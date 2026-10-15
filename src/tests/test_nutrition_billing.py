import pytest
from django.urls import reverse
from django.utils import timezone

from apps.tenancy.models import (
    ConsentRecord,
    DietitianStudentAssignment,
    ProfessionalCredential,
    RoleAssignment,
)
from tests.conftest import authenticate, make_member


def plan_payload(student_id):
    return {
        "student": str(student_id),
        "objective": "Organizar refeições",
        "starts_on": str(timezone.localdate()),
        "draft": {
            "change_reason": "Plano inicial",
            "meal_slots": [
                {
                    "day": 1,
                    "name": "Café da manhã",
                    "order": 1,
                    "foods": [
                        {"description": "Fruta da preferência", "quantity": "1", "unit": "unidade"}
                    ],
                }
            ],
        },
    }


@pytest.mark.django_db
def test_only_verified_assigned_dietitian_can_publish(client, tenant, coach_member, student_member):
    student, _ = student_member
    authenticate(client, coach_member)
    denied = client.post(reverse("nutrition:plan-list"), plan_payload(student.id), format="json")
    assert denied.status_code == 403

    dietitian_member = make_member(
        tenant=tenant, email="diet@example.com", roles=[RoleAssignment.Role.DIETITIAN]
    )
    dietitian, _ = dietitian_member
    DietitianStudentAssignment.objects.create(tenant=tenant, dietitian=dietitian, student=student)
    ConsentRecord.objects.create(tenant=tenant, subject=student, purpose="nutrition_plan")
    credential = ProfessionalCredential.objects.create(
        tenant=tenant, professional=dietitian, kind="crn", registration_number="12345", state="SP"
    )
    authenticate(client, dietitian_member)
    unverified = client.post(
        reverse("nutrition:plan-list"), plan_payload(student.id), format="json"
    )
    assert unverified.status_code == 403
    credential.verified_at = timezone.now()
    credential.save(update_fields=("verified_at",))
    created = client.post(reverse("nutrition:plan-list"), plan_payload(student.id), format="json")
    assert created.status_code == 201, created.data
    published = client.post(reverse("nutrition:plan-publish", args=[created.data["id"]]))
    assert published.status_code == 200
    revised = client.post(
        reverse("nutrition:plan-revise", args=[created.data["id"]]),
        {
            "change_reason": "Ajuste de rotina",
            "meal_slots": [
                {
                    "day": 1,
                    "name": "Almoço",
                    "order": 1,
                    "foods": [{"description": "Refeição combinada"}],
                }
            ],
        },
        format="json",
    )
    assert revised.status_code == 201, revised.data
    assert revised.data["version"] == 2

    authenticate(client, student_member)
    visible = client.get(reverse("nutrition:plan-list"))
    assert visible.status_code == 200
    assert len(visible.data["results"]) == 1
    assert visible.data["results"][0]["active_version"]["version"] == 1


@pytest.mark.django_db
def test_student_cannot_access_academy_billing(client, student_member):
    authenticate(client, student_member)
    response = client.get(reverse("billing:subscription-list"))
    assert response.status_code == 403


@pytest.mark.django_db
def test_unconfigured_provider_rejects_fake_webhook(client):
    response = client.post(
        reverse("billing:webhook", args=["fake"]),
        data={"id": "evt_1"},
        format="json",
        HTTP_X_BILLING_SIGNATURE="invalid",
    )
    assert response.status_code == 403
