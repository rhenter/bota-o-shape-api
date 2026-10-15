from django.contrib import admin

from apps.tenancy.admin_utils import TenantScopedAdmin

from .models import (
    Equipment,
    Exercise,
    ExerciseLog,
    ExerciseMedia,
    ExerciseVariant,
    MuscleGroup,
    SetLog,
    SetPrescription,
    WorkoutAssignment,
    WorkoutDay,
    WorkoutExercise,
    WorkoutSession,
    WorkoutTemplate,
)

for model in (
    Equipment,
    MuscleGroup,
    Exercise,
    ExerciseVariant,
    ExerciseMedia,
    WorkoutTemplate,
    WorkoutDay,
    WorkoutExercise,
    SetPrescription,
    WorkoutAssignment,
    WorkoutSession,
    ExerciseLog,
    SetLog,
):
    admin.site.register(model, TenantScopedAdmin)
