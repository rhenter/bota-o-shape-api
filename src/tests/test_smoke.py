import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient


def test_health_check():
    response = APIClient().get(reverse("core:health"))
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.django_db
def test_user_api_requires_staff():
    response = APIClient().get(reverse("user:user-list"))
    assert response.status_code in {401, 403}


@pytest.mark.django_db
def test_staff_can_create_list_and_update_user():
    user_model = get_user_model()
    staff = user_model.objects.create_user("staff", password="staff-secret", is_staff=True)
    client = APIClient()
    client.force_authenticate(staff)

    created = client.post(
        reverse("user:user-list"),
        {"username": "new-user", "email": "new@example.com", "password": "safe-password-123"},
        format="json",
    )
    assert created.status_code == 201
    assert "password" not in created.data

    new_user = user_model.objects.get(username="new-user")
    assert new_user.check_password("safe-password-123")

    listed = client.get(reverse("user:user-list"))
    assert listed.status_code == 200
    assert any(item["username"] == "new-user" for item in listed.data["results"])

    updated = client.patch(
        reverse("user:user-detail", args=[new_user.pk]),
        {"first_name": "New", "password": "another-safe-password-123"},
        format="json",
    )
    assert updated.status_code == 200
    new_user.refresh_from_db()
    assert new_user.first_name == "New"
    assert new_user.check_password("another-safe-password-123")
