from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.tenancy.models import CoachStudentAssignment
from apps.workouts.models import Exercise, MuscleGroup, WorkoutAssignment, WorkoutTemplate
from tests.conftest import authenticate


@pytest.mark.django_db
def test_workout_observation_version_assignment_and_idempotent_log(
    client, tenant, coach_member, student_member
):
    coach, _ = coach_member
    student, _ = student_member
    CoachStudentAssignment.objects.create(tenant=tenant, coach=coach, student=student)
    muscle = MuscleGroup.objects.create(tenant=tenant, name="Peitoral")
    exercise = Exercise.objects.create(
        tenant=tenant, name="Supino", tracking_type=Exercise.TrackingType.LOAD_REPS
    )
    exercise.primary_muscles.add(muscle)
    authenticate(client, coach_member)
    created = client.post(
        reverse("workouts:workouttemplate-list"),
        {
            "name": "Treino A",
            "days": [
                {
                    "name": "Dia 1",
                    "order": 1,
                    "exercises": [
                        {
                            "exercise": str(exercise.id),
                            "order": 1,
                            "coach_observation": "Mantenha as escápulas estáveis.",
                            "sets": [
                                {
                                    "order": 1,
                                    "repetitions_min": 8,
                                    "repetitions_max": 10,
                                    "note": "Aquecimento",
                                }
                            ],
                        }
                    ],
                }
            ],
        },
        format="json",
    )
    assert created.status_code == 201, created.data
    template_id = created.data["id"]
    published = client.post(reverse("workouts:workouttemplate-publish", args=[template_id]))
    assert published.status_code == 200
    assert published.data["days"][0]["exercises"][0]["coach_observation"].startswith("Mantenha")
    assert published.data["days"][0]["exercises"][0]["sets"][0]["note"] == "Aquecimento"
    revised = client.post(reverse("workouts:workouttemplate-revise", args=[template_id]))
    assert revised.status_code == 201
    assert revised.data["version"] == 2
    assert revised.data["days"][0]["exercises"][0]["coach_observation"].startswith("Mantenha")

    today = timezone.localdate()
    assignment = client.post(
        reverse("workouts:workoutassignment-list"),
        {
            "template": template_id,
            "student": str(student.id),
            "starts_on": str(today),
            "ends_on": str(today + timedelta(days=7)),
        },
    )
    assert assignment.status_code == 201, assignment.data
    authenticate(client, student_member)
    payload = {
        "assignment": assignment.data["id"],
        "idempotency_key": "mobile-1",
        "started_at": timezone.now().isoformat(),
        "exercise_logs": [],
    }
    first = client.post(reverse("workouts:session-list"), payload, format="json")
    second = client.post(reverse("workouts:session-list"), payload, format="json")
    assert first.status_code == 201
    assert second.status_code == 200
    assert first.data["id"] == second.data["id"]
    assert WorkoutAssignment.objects.count() == 1
    assert WorkoutTemplate.objects.count() == 2
