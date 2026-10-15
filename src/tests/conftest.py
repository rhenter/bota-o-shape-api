from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.billing.models import AcademySubscription, BillingPlan
from apps.tenancy.models import Membership, RoleAssignment, Tenant


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def plan(db):
    return BillingPlan.objects.create(
        code="test",
        name="Test",
        features=["workouts", "assessments", "nutrition"],
        limits={"units": 5, "active_students": 100, "team_members": 20},
    )


def make_member(*, tenant, email, roles):
    user = get_user_model().objects.create_user(
        username=email, email=email, password="safe-password-123"
    )
    membership = Membership.objects.create(
        tenant=tenant, user=user, status=Membership.Status.ACTIVE
    )
    RoleAssignment.objects.bulk_create(
        [RoleAssignment(membership=membership, role=role) for role in roles]
    )
    return user, membership


@pytest.fixture
def tenant(plan):
    tenant = Tenant.objects.create(name="Academia A", cnpj="12345678000190")
    AcademySubscription.objects.create(
        tenant=tenant,
        plan=plan,
        status=AcademySubscription.Status.ACTIVE,
        current_period_end=timezone.now() + timedelta(days=30),
    )
    return tenant


@pytest.fixture
def admin_member(tenant):
    return make_member(
        tenant=tenant,
        email="admin@example.com",
        roles=[RoleAssignment.Role.ADMIN, RoleAssignment.Role.BILLING_MANAGE],
    )


@pytest.fixture
def coach_member(tenant):
    return make_member(tenant=tenant, email="coach@example.com", roles=[RoleAssignment.Role.COACH])


@pytest.fixture
def student_member(tenant):
    return make_member(
        tenant=tenant, email="student@example.com", roles=[RoleAssignment.Role.STUDENT]
    )


def authenticate(client, member):
    user, membership = member
    client.force_authenticate(user)
    client.credentials(HTTP_X_TENANT_ID=str(membership.tenant_id))
    return client
