# ======================================================================
# CUSTOMERS APP TESTS (pytest + pytest-django)
#
# Covers: groups and roles, JWT authentication, IDOR / role-based access,
# create and update, validation, search, ordering and pagination.
# Run with:  python -m pytest customers -v
# ======================================================================

# timedelta lets us build an access token that has already expired.
from datetime import timedelta

import pytest
from django.contrib.auth.models import Group
# The cache holds the throttle counters, so tests clear it (see the fixture).
from django.core.cache import cache
# APIClient sends requests to the API without starting a server.
from rest_framework.test import APIClient
# AccessToken lets a test create a real signed token for a user.
from rest_framework_simplejwt.tokens import AccessToken

from .models import Customer, User

# The customers endpoint as mounted by api/urls.py.
URL = "/api/customers/"
# One password for every test user; it never leaves the test database.
PASSWORD = "Pass12345!"


# ======================================================================
# FIXTURES AND HELPERS
# ======================================================================

@pytest.fixture(autouse=True)
def clear_throttle_cache():
    # Anonymous requests are limited to 20/hour. The counters live in the
    # cache, so clear them before every test; otherwise one test's requests
    # could cause a 429 in another.
    cache.clear()


def make_user(username, role):
    # role="admin" / "agent" also places the user in the matching group,
    # because User.save() calls sync_role_group(). is_staff=True is needed
    # because User.is_agent_or_admin checks it.
    return User.objects.create_user(username, password=PASSWORD, role=role, is_staff=True)


@pytest.fixture
def admin(db):
    # An Admin: can see and change every customer.
    return make_user("boss", "admin")


@pytest.fixture
def agent1(db):
    # A Support Agent who owns the first customer.
    return make_user("agent1", "agent")


@pytest.fixture
def agent2(db):
    # A second Support Agent, used to prove agents cannot see each other's data.
    return make_user("agent2", "agent")

# ===  ISP-2 / ISP-146   ===
@pytest.fixture
def customers(agent1, agent2):
    """One customer per agent: (agent1's, agent2's)."""
    def build(n, agent):
        return Customer.objects.create(
            first_name=f"First{n}", last_name=f"Last{n}", email=f"c{n}@x.com",
            phone_number="0821234567", address="1 Long St", assigned_agent=agent,
        )
    return build(1, agent1), build(2, agent2)


def client_for(user):
    """An API client logged in as the given user (skips the token step)."""
    client = APIClient()
    client.force_authenticate(user)
    return client


def payload(**overrides):
    """A valid customer body; each test overrides only what it checks."""
    data = {
        "first_name": "Lerato", "last_name": "Dlamini", "email": "l@x.com",
        "phone_number": "0831112222", "address": "3 Main Rd",
    }
    data.update(overrides)
    return data


def make_bulk_customers(agent, count=25):
    """Create many customers at once, for the pagination tests."""
    for i in range(count):
        Customer.objects.create(
            first_name="Bulk", last_name=f"N{i:02d}", email=f"bulk{i}@x.com",
            phone_number="0821234567", address="x", assigned_agent=agent,
        )


# ======================================================================
# GROUPS AND ROLES
# ======================================================================

def test_groups_exist_after_migrations(db):
    # Created by the 0002_create_groups data migration, so never run
    # pytest with --nomigrations.
    names = set(Group.objects.filter(name__in=["Admin", "Support Agent"])
                .values_list("name", flat=True))
    assert names == {"Admin", "Support Agent"}


def test_role_puts_user_in_group(admin, agent1):
    # The role column and the Django groups must agree.
    assert admin.groups.filter(name="Admin").exists()
    assert agent1.groups.filter(name="Support Agent").exists()


def test_changing_role_moves_group(agent1):
    # Promoting a user moves them to the new group and out of the old one.
    agent1.role = "admin"
    agent1.save()
    assert agent1.groups.filter(name="Admin").exists()
    assert not agent1.groups.filter(name="Support Agent").exists()

# ===  ISP-2 / ISP-14   ===
# ======================================================================
# AUTHENTICATION (JWT)
# ======================================================================

def test_no_token_gets_401(db):
    # Every endpoint needs a JWT.
    assert APIClient().get(URL).status_code == 401


def test_login_returns_access_and_refresh(agent1):
    # Staff log in with username + password and receive both tokens.
    response = APIClient().post(
        "/api/auth/token/", {"username": "agent1", "password": PASSWORD}
    )
    assert response.status_code == 200
    assert "access" in response.data and "refresh" in response.data


def test_wrong_password_gets_401(agent1):
    response = APIClient().post(
        "/api/auth/token/", {"username": "agent1", "password": "wrong"}
    )
    assert response.status_code == 401


def test_user_without_role_gets_403(db):
    # Logged in, but neither Admin nor Support Agent: refused with 403.
    nobody = User.objects.create_user("nobody", password=PASSWORD, is_staff=True)
    assert client_for(nobody).get(URL).status_code == 403


def test_role_only_agent_is_allowed(db):
    # role="agent" with no group yet must still reach the API, because
    # is_agent() checks the role column as well as the group.
    user = User.objects.create_user("roleonly", password=PASSWORD, is_staff=True)
    User.objects.filter(pk=user.pk).update(role="agent")  # update() skips the group sync
    user.refresh_from_db()
    assert client_for(user).get(URL).status_code == 200


def test_invalid_token_returns_json_401(db):
    # A made-up token must give a JSON error, never an HTML page.
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Bearer not-a-real-token")
    response = client.get(URL)
    assert response.status_code == 401
    assert response["Content-Type"].startswith("application/json")
    # "code" comes from the shared handler in api/exceptions.py.
    assert response.data["code"] == "token_not_valid"


def test_expired_token_returns_json_401(agent1):
    # Build a real token, then move its expiry one minute into the past.
    token = AccessToken.for_user(agent1)
    token.set_exp(lifetime=-timedelta(minutes=1))
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    response = client.get(URL)
    assert response.status_code == 401
    assert response.data["code"] == "token_not_valid"
    # The handler turns simplejwt's reason into a readable message.
    assert "expired" in response.data["detail"].lower()

# ===  ISP-2 / ISP-146   ===
# ======================================================================
# IDOR / ROLE-BASED ACCESS
# ======================================================================

def test_agent_lists_only_own_customers(agent1, customers):
    # Queryset filtering: agent1 sees one customer, not agent2's.
    response = client_for(agent1).get(URL)
    assert response.data["count"] == 1
    assert response.data["results"][0]["email"] == "c1@x.com"


def test_second_agent_sees_only_theirs(agent2, customers):
    response = client_for(agent2).get(URL)
    assert response.data["count"] == 1
    assert response.data["results"][0]["email"] == "c2@x.com"


def test_admin_lists_everything(admin, customers):
    # Admins are not filtered.
    assert client_for(admin).get(URL).data["count"] == 2

# ===  ISP-150   ===
def test_agent_cannot_read_other_agents_customer(agent1, customers):
    # The required IDOR test: 403, not 404.
    assert client_for(agent1).get(f"{URL}{customers[1].pk}/").status_code == 403


def test_agent_can_read_own_customer(agent1, customers):
    assert client_for(agent1).get(f"{URL}{customers[0].pk}/").status_code == 200


def test_agent_cannot_patch_other_agents_customer(agent1, customers):
    # Writes are protected the same way as reads.
    response = client_for(agent1).patch(f"{URL}{customers[1].pk}/", {"address": "x"})
    assert response.status_code == 403


def test_admin_can_read_any_customer(admin, customers):
    assert client_for(admin).get(f"{URL}{customers[1].pk}/").status_code == 200


def test_unknown_id_gets_404(agent1):
    # A well-formed id that does not exist is 404 (not 403).
    response = client_for(agent1).get(f"{URL}3f2a4c1e-0000-4000-8000-000000000000/")
    assert response.status_code == 404


def test_agent_cannot_delete_even_own_customer(agent1, customers):
    # Only Admins may delete; the record must still exist afterwards.
    assert client_for(agent1).delete(f"{URL}{customers[0].pk}/").status_code == 403
    assert Customer.objects.filter(pk=customers[0].pk).exists()


def test_admin_can_delete(admin, customers):
    assert client_for(admin).delete(f"{URL}{customers[0].pk}/").status_code == 204


# ======================================================================
# CREATE AND UPDATE
# ======================================================================

def test_create_assigns_requesting_user_and_ignores_client_value(agent1, agent2):
    # The client tries to assign the customer to agent2; the server ignores it.
    response = client_for(agent1).post(URL, payload(assigned_agent=agent2.pk))
    assert response.status_code == 201
    assert Customer.objects.get(email="l@x.com").assigned_agent == agent1


def test_agent_can_update_own_customer(agent1, customers):
    # PATCH changes only the fields that are sent.
    response = client_for(agent1).patch(f"{URL}{customers[0].pk}/", {"address": "9 New Rd"})
    assert response.status_code == 200
    customers[0].refresh_from_db()
    assert customers[0].address == "9 New Rd"


def test_admin_can_update_any_customer(admin, customers):
    response = client_for(admin).patch(f"{URL}{customers[1].pk}/", {"address": "Admin St"})
    assert response.status_code == 200


def test_put_replaces_all_fields(agent1, customers):
    # PUT needs every field. Keep the same email so it is not a duplicate.
    response = client_for(agent1).put(f"{URL}{customers[0].pk}/", payload(email="c1@x.com"))
    assert response.status_code == 200
    assert response.data["first_name"] == "Lerato"


def test_agent_cannot_reassign_owner_on_update(agent1, agent2, customers):
    # assigned_agent is read-only, so the client's value is ignored.
    client_for(agent1).patch(f"{URL}{customers[0].pk}/", {"assigned_agent": agent2.pk})
    customers[0].refresh_from_db()
    assert customers[0].assigned_agent == agent1

# ===  ISP-2 / ISP-148   ===
# ======================================================================
# VALIDATION (400 with a clear message)
# ======================================================================

@pytest.mark.parametrize(
    "bad_phone",
    [
        "082123456",           # 9 digits: too short
        "08212345ab",          # letters
        "1234567890123456",    # 16 digits: too long
        "+27 82",              # formatted but too few digits
        "0821234567#",         # disallowed symbol
    ],
)
def test_invalid_phone_rejected(agent1, bad_phone):
    response = client_for(agent1).post(URL, payload(phone_number=bad_phone))
    assert response.status_code == 400
    assert "phone_number" in response.data


def test_formatted_phone_accepted(agent1):
    # Spaces, brackets, hyphens and a leading + are fine with 10+ digits.
    response = client_for(agent1).post(URL, payload(phone_number="+27 (82) 123-4567"))
    assert response.status_code == 201


def test_invalid_email_rejected(agent1):
    response = client_for(agent1).post(URL, payload(email="not-an-email"))
    assert response.status_code == 400
    # "code" comes from the shared handler in api/exceptions.py.
    assert response.data["code"] == "validation_error"
    assert "email" in response.data


def test_duplicate_email_rejected_ignoring_case(agent1, customers):
    # "C1@X.COM" clashes with the existing "c1@x.com".
    response = client_for(agent1).post(URL, payload(email="C1@X.COM"))
    assert response.status_code == 400


# ======================================================================
# SEARCH, FILTERING, ORDERING AND PAGINATION
# ======================================================================

def test_search_by_name(admin, customers):
    response = client_for(admin).get(URL, {"search": "Last2"})
    assert response.data["count"] == 1


def test_search_by_email_and_phone(admin, customers):
    assert client_for(admin).get(URL, {"search": "c1@x.com"}).data["count"] == 1
    # Both customers share the same phone number.
    assert client_for(admin).get(URL, {"search": "0821234567"}).data["count"] == 2


def test_search_cannot_widen_an_agents_list(agent1, customers):
    # Search runs on top of the scoped queryset, so agent1 never finds agent2's customer.
    response = client_for(agent1).get(URL, {"search": "Last2"})
    assert response.data["count"] == 0


def test_filter_by_assigned_agent(admin, agent1, customers):
    response = client_for(admin).get(URL, {"assigned_agent": agent1.pk})
    assert response.data["count"] == 1


def test_ordering_descending(admin, customers):
    # A leading "-" sorts Z to A.
    response = client_for(admin).get(URL, {"ordering": "-last_name"})
    assert response.data["results"][0]["last_name"] == "Last2"


def test_pagination_is_20_per_page(admin, agent1):
    make_bulk_customers(agent1)
    response = client_for(admin).get(URL)
    assert response.data["count"] == 25
    assert len(response.data["results"]) == 20


def test_page_two_has_remaining_records(admin, agent1):
    make_bulk_customers(agent1)
    response = client_for(admin).get(URL, {"page": 2})
    assert len(response.data["results"]) == 5