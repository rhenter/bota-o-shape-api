from django.db import transaction
from rest_framework import serializers

from .models import (
    Equipment,
    Exercise,
    ExerciseLog,
    MuscleGroup,
    SetLog,
    SetPrescription,
    WorkoutAssignment,
    WorkoutDay,
    WorkoutExercise,
    WorkoutSession,
    WorkoutTemplate,
)


class EquipmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Equipment
        exclude = ("tenant",)


class MuscleGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = MuscleGroup
        exclude = ("tenant",)


class ExerciseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Exercise
        exclude = ("tenant",)


class SetPrescriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SetPrescription
        exclude = ("tenant", "workout_exercise")

    def validate(self, attrs):
        if attrs.get("repetitions_min") and attrs.get("repetitions_max"):
            if attrs["repetitions_min"] > attrs["repetitions_max"]:
                raise serializers.ValidationError(
                    "O mínimo de repetições não pode superar o máximo."
                )
        return attrs


class WorkoutExerciseSerializer(serializers.ModelSerializer):
    sets = SetPrescriptionSerializer(many=True)
    exercise_name = serializers.CharField(source="exercise.name", read_only=True)

    class Meta:
        model = WorkoutExercise
        exclude = ("tenant", "day")


class WorkoutDaySerializer(serializers.ModelSerializer):
    exercises = WorkoutExerciseSerializer(many=True)

    class Meta:
        model = WorkoutDay
        exclude = ("tenant", "template")


class WorkoutTemplateSerializer(serializers.ModelSerializer):
    days = WorkoutDaySerializer(many=True, required=False)

    class Meta:
        model = WorkoutTemplate
        exclude = ("tenant", "author")
        read_only_fields = ("status", "version", "published_at", "supersedes")

    @transaction.atomic
    def create(self, validated_data):
        days = validated_data.pop("days", [])
        template = WorkoutTemplate.objects.create(**validated_data)
        self._create_days(template, days)
        return template

    def _create_days(self, template, days):
        for day_data in days:
            exercises = day_data.pop("exercises")
            day = WorkoutDay.objects.create(tenant=template.tenant, template=template, **day_data)
            for exercise_data in exercises:
                sets = exercise_data.pop("sets")
                for key in ("exercise", "variant", "alternative"):
                    related = exercise_data.get(key)
                    if related is not None and related.tenant_id != template.tenant_id:
                        raise serializers.ValidationError(
                            {key: "O item deve pertencer à academia ativa."}
                        )
                prescribed = WorkoutExercise.objects.create(
                    tenant=template.tenant, day=day, **exercise_data
                )
                SetPrescription.objects.bulk_create(
                    [
                        SetPrescription(
                            tenant=template.tenant, workout_exercise=prescribed, **set_data
                        )
                        for set_data in sets
                    ]
                )


class WorkoutAssignmentSerializer(serializers.ModelSerializer):
    template_detail = WorkoutTemplateSerializer(source="template", read_only=True)

    class Meta:
        model = WorkoutAssignment
        exclude = ("tenant", "assigned_by")


class SetLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = SetLog
        exclude = ("tenant", "exercise_log")


class ExerciseLogSerializer(serializers.ModelSerializer):
    set_logs = SetLogSerializer(many=True, required=False)

    class Meta:
        model = ExerciseLog
        exclude = ("tenant", "session")


class WorkoutSessionSerializer(serializers.ModelSerializer):
    exercise_logs = ExerciseLogSerializer(many=True, required=False)

    class Meta:
        model = WorkoutSession
        exclude = ("tenant", "student")

    @transaction.atomic
    def create(self, validated_data):
        logs = validated_data.pop("exercise_logs", [])
        session = WorkoutSession.objects.create(**validated_data)
        for log_data in logs:
            set_logs = log_data.pop("set_logs", [])
            exercise_log = ExerciseLog.objects.create(
                tenant=session.tenant, session=session, **log_data
            )
            SetLog.objects.bulk_create(
                [
                    SetLog(tenant=session.tenant, exercise_log=exercise_log, **item)
                    for item in set_logs
                ]
            )
        return session
