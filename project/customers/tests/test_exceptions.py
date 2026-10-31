
import pytest

from django.db import IntegrityError
from rest_framework.test import APIRequestFactory

from customers.exceptions import custom_exception_handler


# --------------------------------------------------
# SAFE ERROR HANDLING TESTS
# --------------------------------------------------

@pytest.mark.django_db
def test_integrity_error_returns_400():
    factory = APIRequestFactory()
    request = factory.post("/api/customers/")

    exc = IntegrityError(
        "Internal database details"
    )

    response = custom_exception_handler(
        exc,
        {"request": request},
    )

    assert response.status_code == 400
    assert response.data["error"]["code"] == (
        "integrity_error"
    )

    # Internal database details must not be exposed.
    assert "Internal database details" not in str(
        response.data
    )


def test_unexpected_error_returns_safe_500():
    factory = APIRequestFactory()
    request = factory.get("/api/customers/")

    exc = RuntimeError(
        "Sensitive internal information"
    )

    response = custom_exception_handler(
        exc,
        {"request": request},
    )

    assert response.status_code == 500
    assert response.data["error"]["code"] == (
        "internal_server_error"
    )

    assert "Sensitive internal information" not in str(
        response.data
    )
