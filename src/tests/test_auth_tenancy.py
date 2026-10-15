import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse

from apps.billing.models import AcademySubscription
from apps.tenancy.models import GymUnit, Membership, RoleAssignment
from tests.conftest import authenticate, make_member


def test_health_check(client):
    response = client.get(reverse("core:health"))
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.django_db
def test_owner_registration_creates_pilot_and_jwt_login(client):
    response = client.post(
        reverse("tenancy:owner-register"),
        {
            "tenant_name": "Bota o Shape Centro",
            "cnpj": "12345678000199",
            "email": "owner@example.com",
            "password": "safe-password-123",
            "first_name": "Owner",
        },
    )
    assert response.status_code == 201
    membership = Membership.objects.get(user__email="owner@example.com")
    assert set(membership.role_assignments.values_list("role", flat=True)) == {
        RoleAssignment.Role.OWNER,
        RoleAssignment.Role.ADMIN,
        RoleAssignment.Role.BILLING_MANAGE,
    }
    assert AcademySubscription.objects.get(tenant=membership.tenant).status == "pilot"
    login = client.post(
        reverse("user:token-obtain"),
        {"email": "owner@example.com", "password": "safe-password-123"},
    )
    assert login.status_code == 200
    assert {"access", "refresh"} <= set(login.data)


@pytest.mark.django_db
def test_admin_invites_student_without_student_checkout(client, admin_member, settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    authenticate(client, admin_member)
    response = client.post(
        reverse("tenancy:membership-invite"),
        {"email": "new-student@example.com", "roles": ["student"]},
    )
    assert response.status_code == 201
    token = mail.outbox[0].body.rsplit(" ", 1)[-1]
    client.force_authenticate(None)
    client.credentials()
    accepted = client.post(
        reverse("tenancy:invitation-accept"),
        {
            "token": token,
            "password": "student-password-123",
            "first_name": "Student",
        },
    )
    assert accepted.status_code == 201
    assert Membership.objects.get(user__email="new-student@example.com").status == "active"


@pytest.mark.django_db
def test_tenant_header_prevents_cross_tenant_access(client, admin_member, plan):
    user, _ = admin_member
    other = admin_member[1].tenant.__class__.objects.create(name="Other")
    AcademySubscription.objects.create(tenant=other, plan=plan, status="active")
    make_member(tenant=other, email="other@example.com", roles=["admin"])
    foreign_unit = GymUnit.objects.create(tenant=other, name="Foreign")
    client.force_authenticate(user)
    client.credentials(HTTP_X_TENANT_ID=str(other.id))
    assert client.get(reverse("tenancy:unit-detail", args=[foreign_unit.id])).status_code == 403


@pytest.mark.django_db
def test_password_reset_never_reveals_account_existence(client):
    response = client.post(reverse("user:password-reset"), {"email": "missing@example.com"})
    assert response.status_code == 200
    assert "existir" in response.data["detail"]
    assert get_user_model().objects.count() == 0
