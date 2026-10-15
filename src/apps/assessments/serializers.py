from django.db import transaction
from rest_framework import serializers

from .models import Assessment, AssessmentReport, Measurement, MeasurementProtocol


class MeasurementProtocolSerializer(serializers.ModelSerializer):
    class Meta:
        model = MeasurementProtocol
        exclude = ("tenant",)


class MeasurementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Measurement
        exclude = ("tenant", "assessment")

    def validate(self, attrs):
        method = attrs.get("method", getattr(self.instance, "method", ""))
        site = attrs.get("anatomical_site", getattr(self.instance, "anatomical_site", ""))
        if method in {"skinfold", "circumference"} and not site:
            raise serializers.ValidationError({"anatomical_site": "Informe o ponto anatômico."})
        metric = attrs.get("metric", "")
        value = attrs.get("raw_value")
        if (
            metric == "body_fat_percentage"
            and value is not None
            and not attrs.get("equation_metadata")
        ):
            raise serializers.ValidationError(
                {"equation_metadata": "Percentual calculado exige equação e responsável."}
            )
        attrs["possible_error"] = bool(value is not None and (value < 0 or value > 10000))
        return attrs


class AssessmentSerializer(serializers.ModelSerializer):
    measurements = MeasurementSerializer(many=True, required=False)

    class Meta:
        model = Assessment
        exclude = ("tenant", "evaluator")
        read_only_fields = ("status", "released_at")

    @transaction.atomic
    def create(self, validated_data):
        measurements = validated_data.pop("measurements", [])
        assessment = Assessment.objects.create(**validated_data)
        Measurement.objects.bulk_create(
            [
                Measurement(tenant=assessment.tenant, assessment=assessment, **item)
                for item in measurements
            ]
        )
        return assessment


class AssessmentReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssessmentReport
        exclude = ("tenant", "generated_by")
