from django.conf import settings
from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.models import TenantScopedModel


class Equipment(TenantScopedModel):
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("tenant", "name"), name="unique_tenant_equipment")
        ]


class MuscleGroup(TenantScopedModel):
    name = models.CharField(max_length=100)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("tenant", "name"), name="unique_tenant_muscle")
        ]


class Exercise(TenantScopedModel):
    class TrackingType(models.TextChoices):
        LOAD_REPS = "load_reps", "Load and repetitions"
        BODYWEIGHT_REPS = "bodyweight_reps", "Bodyweight and repetitions"
        DURATION = "duration", "Duration"
        DISTANCE = "distance", "Distance"
        ACTIVITY = "activity", "Activity without load"

    class ReviewStatus(models.TextChoices):
        DRAFT = "draft", "Draft"
        REVIEWED = "reviewed", "Reviewed"
        ARCHIVED = "archived", "Archived"

    name = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    instructions = models.JSONField(default=dict, blank=True)
    movement_pattern = models.CharField(max_length=100, blank=True)
    tracking_type = models.CharField(max_length=24, choices=TrackingType.choices)
    review_status = models.CharField(
        max_length=16, choices=ReviewStatus.choices, default=ReviewStatus.DRAFT
    )
    equipment = models.ManyToManyField(Equipment, blank=True)
    primary_muscles = models.ManyToManyField(MuscleGroup, related_name="primary_exercises")
    secondary_muscles = models.ManyToManyField(
        MuscleGroup, blank=True, related_name="secondary_exercises"
    )

    class Meta:
        indexes = [models.Index(fields=("tenant", "name"))]


class ExerciseVariant(TenantScopedModel):
    exercise = models.ForeignKey(Exercise, on_delete=models.PROTECT, related_name="variants")
    name = models.CharField(max_length=180)
    instructions = models.JSONField(default=dict, blank=True)
    equipment = models.ManyToManyField(Equipment, blank=True)


class ExerciseMedia(TenantScopedModel):
    exercise = models.ForeignKey(Exercise, on_delete=models.PROTECT, related_name="media")
    file = models.FileField(
        upload_to="exercise-media/",
        validators=[FileExtensionValidator(("jpg", "jpeg", "png", "gif", "mp4", "webm"))],
    )
    media_type = models.CharField(max_length=16)
    reviewed = models.BooleanField(default=False)


class WorkoutTemplate(TenantScopedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    name = models.CharField(max_length=180)
    objective = models.CharField(max_length=200, blank=True)
    level = models.CharField(max_length=80, blank=True)
    notes = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    supersedes = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT)
    published_at = models.DateTimeField(null=True, blank=True)


class WorkoutDay(TenantScopedModel):
    template = models.ForeignKey(WorkoutTemplate, on_delete=models.CASCADE, related_name="days")
    name = models.CharField(max_length=120)
    order = models.PositiveIntegerField()

    class Meta:
        ordering = ("order",)
        constraints = [
            models.UniqueConstraint(fields=("template", "order"), name="unique_workout_day_order")
        ]


class WorkoutExercise(TenantScopedModel):
    day = models.ForeignKey(WorkoutDay, on_delete=models.CASCADE, related_name="exercises")
    exercise = models.ForeignKey(Exercise, on_delete=models.PROTECT)
    variant = models.ForeignKey(ExerciseVariant, null=True, blank=True, on_delete=models.PROTECT)
    alternative = models.ForeignKey(
        Exercise, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    order = models.PositiveIntegerField()
    coach_observation = models.TextField(blank=True)

    class Meta:
        ordering = ("order",)
        constraints = [
            models.UniqueConstraint(fields=("day", "order"), name="unique_workout_exercise_order")
        ]


class SetPrescription(TenantScopedModel):
    workout_exercise = models.ForeignKey(
        WorkoutExercise, on_delete=models.CASCADE, related_name="sets"
    )
    order = models.PositiveIntegerField()
    repetitions_min = models.PositiveIntegerField(null=True, blank=True)
    repetitions_max = models.PositiveIntegerField(null=True, blank=True)
    load_kg = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    distance_meters = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True)
    rest_seconds = models.PositiveIntegerField(null=True, blank=True)
    rpe = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
    )
    rir = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MaxValueValidator(10)]
    )
    cadence = models.CharField(max_length=30, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ("order",)
        constraints = [
            models.UniqueConstraint(fields=("workout_exercise", "order"), name="unique_set_order")
        ]


class WorkoutAssignment(TenantScopedModel):
    template = models.ForeignKey(
        WorkoutTemplate, on_delete=models.PROTECT, related_name="assignments"
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="workout_assignments"
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="workouts_assigned"
    )
    starts_on = models.DateField()
    ends_on = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)


class WorkoutSession(TenantScopedModel):
    assignment = models.ForeignKey(
        WorkoutAssignment, on_delete=models.PROTECT, related_name="sessions"
    )
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    idempotency_key = models.CharField(max_length=100)
    started_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)
    student_note = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("tenant", "student", "idempotency_key"), name="unique_workout_request"
            )
        ]


class ExerciseLog(TenantScopedModel):
    session = models.ForeignKey(
        WorkoutSession, on_delete=models.CASCADE, related_name="exercise_logs"
    )
    workout_exercise = models.ForeignKey(WorkoutExercise, on_delete=models.PROTECT)
    skipped = models.BooleanField(default=False)
    note = models.TextField(blank=True)


class SetLog(TenantScopedModel):
    exercise_log = models.ForeignKey(ExerciseLog, on_delete=models.CASCADE, related_name="set_logs")
    prescription = models.ForeignKey(
        SetPrescription, null=True, blank=True, on_delete=models.PROTECT
    )
    repetitions = models.PositiveIntegerField(null=True, blank=True)
    load_kg = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    distance_meters = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True)
    rpe = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
