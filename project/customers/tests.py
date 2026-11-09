import pytest
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from .models import Customer, User

URL = "/api/customers/"
PASSWORD = "Pass12345!"


def make_user(username, role):
    # role="admin" / "agent" also places the user in the matching group (User.save).
    return User.objects.create_user(username, password=PASSWORD, role=role, is_staff=True)


@pytest.fixture
def admin(db):
    return make_user("boss", "admin")


@pytest.fixture
def agent1(db):
    return make_user("agent1", "agent")


@pytest.fixture
def agent2(db):
    return make_user("agent2", "agent")


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
    """An API client logged in as the given user."""
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


# ---------------- groups and roles ----------------

def test_groups_exist(db):
    names = set(Group.objects.filter(name__in=["Admin", "Support Agent"])
                .values_list("name", flat=True))
    assert names == {"Admin", "Support Agent"}


def test_role_puts_user_in_group(admin, agent1):
    assert admin.groups.filter(name="Admin").exists()
    assert agent1.groups.filter(name="Support Agent").exists()


def test_changing_role_moves_group(agent1):
    agent1.role = "admin"
    agent1.save()
    assert agent1.groups.filter(name="Admin").exists()
    assert not agent1.groups.filter(name="Support Agent").exists()


# ---------------- authentication ----------------

def test_no_token_gets_401(db):
    assert APIClient().get(URL).status_code == 401


def test_login_returns_access_and_refresh(agent1):
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
    nobody = User.objects.create_user("nobody", password=PASSWORD, is_staff=True)
    assert client_for(nobody).get(URL).status_code == 403


# ---------------- IDOR / role-based access ----------------

def test_agent_lists_only_own_customers(agent1, customers):
    response = client_for(agent1).get(URL)
    assert response.data["count"] == 1
    assert response.data["results"][0]["email"] == "c1@x.com"


def test_second_agent_sees_only_theirs(agent2, customers):
    response = client_for(agent2).get(URL)
    assert response.data["count"] == 1
    assert response.data["results"][0]["email"] == "c2@x.com"


def test_admin_lists_everything(admin, customers):
    assert client_for(admin).get(URL).data["count"] == 2


def test_agent_cannot_read_other_agents_customer(agent1, customers):
    # The required IDOR test: 403, not 404.
    assert client_for(agent1).get(f"{URL}{customers[1].pk}/").status_code == 403


def test_agent_can_read_own_customer(agent1, customers):
    assert client_for(agent1).get(f"{URL}{customers[0].pk}/").status_code == 200


def test_agent_cannot_patch_other_agents_customer(agent1, customers):
    response = client_for(agent1).patch(f"{URL}{customers[1].pk}/", {"address": "x"})
    assert response.status_code == 403


def test_admin_can_read_any_customer(admin, customers):
    assert client_for(admin).get(f"{URL}{customers[1].pk}/").status_code == 200


def test_unknown_id_gets_404(agent1):
    response = client_for(agent1).get(f"{URL}3f2a4c1e-0000-4000-8000-000000000000/")
    assert response.status_code == 404


def test_agent_cannot_delete_even_own_customer(agent1, customers):
    assert client_for(agent1).delete(f"{URL}{customers[0].pk}/").status_code == 403
    assert Customer.objects.filter(pk=customers[0].pk).exists()


def test_admin_can_delete(admin, customers):
    assert client_for(admin).delete(f"{URL}{customers[0].pk}/").status_code == 204


# ---------------- create / update ----------------

def test_create_assigns_requesting_user_and_ignores_client_value(agent1, agent2, db):
    response = client_for(agent1).post(URL, payload(assigned_agent=agent2.pk))
    assert response.status_code == 201
    assert Customer.objects.get(email="l@x.com").assigned_agent == agent1


def test_agent_can_update_own_customer(agent1, customers):
    response = client_for(agent1).patch(f"{URL}{customers[0].pk}/", {"address": "9 New Rd"})
    assert response.status_code == 200
    customers[0].refresh_from_db()
    assert customers[0].address == "9 New Rd"


# ---------------- validation (400 with a clear message) ----------------

@pytest.mark.parametrize("bad_phone", ["082123456", "08212345ab", "1234567890123456"])
def test_invalid_phone_rejected(agent1, bad_phone):
    response = client_for(agent1).post(URL, payload(phone_number=bad_phone))
    assert response.status_code == 400
    assert "phone_number" in response.data


def test_formatted_phone_accepted(agent1):
    response = client_for(agent1).post(URL, payload(phone_number="+27 (82) 123-4567"))
    assert response.status_code == 201


def test_invalid_email_rejected(agent1):
    response = client_for(agent1).post(URL, payload(email="not-an-email"))
    assert response.status_code == 400
    assert "email" in response.data


def test_duplicate_email_rejected_ignoring_case(agent1, customers):
    response = client_for(agent1).post(URL, payload(email="C1@X.COM"))
    assert response.status_code == 400


# ---------------- search / ordering / pagination ----------------

def test_search_by_name(admin, customers):
    response = client_for(admin).get(URL, {"search": "Last2"})
    assert response.data["count"] == 1


def test_search_by_email_and_phone(admin, customers):
    assert client_for(admin).get(URL, {"search": "c1@x.com"}).data["count"] == 1
    assert client_for(admin).get(URL, {"search": "0821234567"}).data["count"] == 2


def test_ordering_descending(admin, customers):
    response = client_for(admin).get(URL, {"ordering": "-last_name"})
    assert response.data["results"][0]["last_name"] == "Last2"


def test_pagination_is_20_per_page(admin, agent1):
    for i in range(25):
        Customer.objects.create(
            first_name="Bulk", last_name=f"N{i:02d}", email=f"bulk{i}@x.com",
            phone_number="0821234567", address="x", assigned_agent=agent1,
        )
    response = client_for(admin).get(URL)
    assert response.data["count"] == 25
    assert len(response.data["results"]) == 20