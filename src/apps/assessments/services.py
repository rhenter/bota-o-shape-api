from decimal import Decimal

from .models import Assessment


def build_comparisons(assessment):
    previous = Assessment.objects.filter(
        tenant=assessment.tenant,
        student=assessment.student,
        assessed_at__lt=assessment.assessed_at,
        status__in=(Assessment.Status.COMPLETED, Assessment.Status.RELEASED),
    ).order_by("-assessed_at")
    comparisons = []
    for current in assessment.measurements.all():
        prior = None
        for candidate in previous:
            prior = next(
                (
                    m
                    for m in candidate.measurements.all()
                    if m.compatibility_key() == current.compatibility_key()
                ),
                None,
            )
            if prior:
                break
        if not prior:
            comparisons.append(
                {"measurement_id": str(current.id), "comparison_status": "not_comparable"}
            )
            continue
        difference = current.raw_value - prior.raw_value
        percent = None if prior.raw_value == 0 else (difference / prior.raw_value * Decimal("100"))
        comparisons.append(
            {
                "measurement_id": str(current.id),
                "previous_measurement_id": str(prior.id),
                "comparison_status": "increased"
                if difference > 0
                else "decreased"
                if difference < 0
                else "unchanged",
                "difference": str(difference),
                "difference_percent": None
                if percent is None
                else str(percent.quantize(Decimal("0.01"))),
            }
        )
    return comparisons
