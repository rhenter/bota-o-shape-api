from django.db import models


class TimestampedModel(models.Model):
    """Optional abstract base for models that need creation/update timestamps."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
