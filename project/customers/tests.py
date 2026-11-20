# Customers tests (BRD s19: at least 8 to 12 pytest tests, s25 scenarios).
# Run with: pytest customers
import pytest
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.core.management import call_command
from drf_spectacular.generators import SchemaGenerator
from rest_framework.test import APIClient

from .models import Customer, User

URL = "/api/customers/"
PASSWORD = "Pass12345!"


@pytest.fixture(autouse=True)
def clear_throttle_cache():
    # BRD s15 throttles anonymous requests (20/hour). Clear the counters so
    # one test cannot cause a 429 in another.
    cache.clear()


def make_user(username, role):
    # User.save() also adds the user to the matching group.
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


# ---------------- Groups and roles (BRD s7) ----------------
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


# ---------------- Authentication (FR-01, FR-16, TC-01, TC-05) ----------------
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


def test_role_only_agent_is_allowed(db):
    # An agent with no group yet can still use the API, because is_agent()
    # checks the role as well as the group.
    user = User.objects.create_user("roleonly", password=PASSWORD, is_staff=True)
    User.objects.filter(pk=user.pk).update(role="agent")  # skips the group sync
    user.refresh_from_db()
    assert client_for(user).get(URL).status_code == 200


# ---------------- IDOR and role-based access (BRD s15, s18, TC-04) ----------------
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
    # BRD s18 and TC-04: another agent's customer returns 403, not 404.
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


# ---------------- Create and update (FR-03) ----------------
def test_create_assigns_requesting_user_and_ignores_client_value(agent1, agent2, db):
    response = client_for(agent1).post(URL, payload(assigned_agent=agent2.pk))
    assert response.status_code == 201
    assert Customer.objects.get(email="l@x.com").assigned_agent == agent1


def test_agent_can_update_own_customer(agent1, customers):
    response = client_for(agent1).patch(f"{URL}{customers[0].pk}/", {"address": "9 New Rd"})
    assert response.status_code == 200
    customers[0].refresh_from_db()
    assert customers[0].address == "9 New Rd"


# ---------------- Validation: 400 with a clear message (BRD s18) ----------------
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


# ---------------- Search, ordering, pagination (FR-04, BRD s8.2) ----------------
def test_search_by_name(admin, customers):
    response = client_for(admin).get(URL, {"search": "Last2"})
    assert response.data["count"] == 1


def test_search_by_email_and_phone(admin, customers):
    assert client_for(admin).get(URL, {"search": "c1@x.com"}).data["count"] == 1
    assert client_for(admin).get(URL, {"search": "0821234567"}).data["count"] == 2


def test_search_cannot_widen_an_agents_list(agent1, customers):
    # Search runs on the scoped list, so agent1 never finds agent2's customer.
    response = client_for(agent1).get(URL, {"search": "Last2"})
    assert response.data["count"] == 0


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


# ---------------- Swagger documentation (FR-17, BRD s17) ----------------

DOCS_URL = "/api/docs/"
LIST_PATH = "/api/customers/"


@pytest.fixture(scope="module")
def schema():
    """Build the OpenAPI schema once for all the docs tests."""
    return SchemaGenerator().get_schema(request=None, public=True)


@pytest.fixture
def detail_path(schema):
    """The customer detail path, e.g. /api/customers/{id}/."""
    paths = [p for p in schema["paths"] if p.startswith(LIST_PATH) and "{" in p]
    assert len(paths) == 1, f"expected one customers detail path, got {paths}"
    return paths[0]


def test_swagger_page_loads(db):
    assert APIClient().get(DOCS_URL).status_code == 200


def test_schema_is_openapi_3(schema):
    assert schema["openapi"].startswith("3.")
    assert schema["info"]["title"]


def test_schema_has_no_errors(tmp_path, db):
    # Same as: manage.py spectacular --validate. Errors fail; warnings from
    # other apps do not.
    call_command("spectacular", validate=True, file=str(tmp_path / "schema.yml"))


def test_list_path_documents_get_and_post(schema):
    assert {"get", "post"} <= set(schema["paths"][LIST_PATH])


def test_detail_path_documents_get_put_patch_delete(schema, detail_path):
    assert {"get", "put", "patch", "delete"} <= set(schema["paths"][detail_path])


def test_every_customers_operation_has_tag_and_summary(schema, detail_path):
    for path in (LIST_PATH, detail_path):
        for method, operation in schema["paths"][path].items():
            if method == "parameters":
                continue
            assert operation.get("tags"), f"{method.upper()} {path}: no tag"
            assert operation.get("summary"), f"{method.upper()} {path}: no summary"


def test_customer_id_path_parameter_is_a_uuid(schema, detail_path):
    operation = schema["paths"][detail_path]["get"]
    path_params = [p for p in operation["parameters"] if p["in"] == "path"]
    assert len(path_params) == 1   # no duplicate id parameter
    assert path_params[0]["schema"]["format"] == "uuid"


def test_list_documents_search_ordering_and_page_parameters(schema):
    names = {p["name"] for p in schema["paths"][LIST_PATH]["get"]["parameters"]}
    assert {"search", "ordering", "page"} <= names


def test_success_status_codes_documented(schema, detail_path):
    assert "201" in schema["paths"][LIST_PATH]["post"]["responses"]
    assert "200" in schema["paths"][LIST_PATH]["get"]["responses"]
    assert "200" in schema["paths"][detail_path]["get"]["responses"]
    assert "204" in schema["paths"][detail_path]["delete"]["responses"]


def test_error_status_codes_documented(schema, detail_path):
    post = schema["paths"][LIST_PATH]["post"]["responses"]
    get_one = schema["paths"][detail_path]["get"]["responses"]
    assert {"400", "401"} <= set(post)
    assert {"401", "403", "404"} <= set(get_one)


def test_list_response_is_paginated(schema):
    ok = schema["paths"][LIST_PATH]["get"]["responses"]["200"]
    body = ok["content"]["application/json"]["schema"]
    component = body["$ref"].split("/")[-1]
    properties = schema["components"]["schemas"][component]["properties"]
    assert {"count", "next", "previous", "results"} <= set(properties)


def test_customer_schema_lists_fields_and_read_only_ones(schema):
    props = schema["components"]["schemas"]["Customer"]["properties"]
    assert {"first_name", "last_name", "email", "phone_number", "address"} <= set(props)
    # The server sets these, so Swagger must not offer them as input.
    assert props["assigned_agent"].get("readOnly") is True
    assert props["customer_id"].get("readOnly") is True


def test_create_request_has_an_example(schema):
    body = schema["paths"][LIST_PATH]["post"]["requestBody"]["content"]["application/json"]
    assert body.get("examples") or body["schema"].get("example")


def test_bearer_jwt_security_scheme_documented(schema):
    schemes = schema["components"]["securitySchemes"]
    assert any(s.get("type") == "http" and s.get("scheme", "").lower() == "bearer"
               for s in schemes.values())
