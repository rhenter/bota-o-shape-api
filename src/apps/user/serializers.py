from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import serializers

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "first_name", "last_name", "email", "is_active", "date_joined")
        read_only_fields = ("id", "email", "is_active", "date_joined")


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        try:
            user_id = force_str(urlsafe_base64_decode(attrs["uid"]))
            user = User.objects.get(pk=user_id, is_active=True)
        except ValueError, TypeError, OverflowError, User.DoesNotExist:
            raise serializers.ValidationError({"token": "Token inválido ou expirado."}) from None
        if not default_token_generator.check_token(user, attrs["token"]):
            raise serializers.ValidationError({"token": "Token inválido ou expirado."})
        validate_password(attrs["password"], user)
        attrs["user"] = user
        return attrs

    def save(self):
        user = self.validated_data["user"]
        user.set_password(self.validated_data["password"])
        user.must_reset_password = False
        user.save(update_fields=("password", "must_reset_password"))
        return user
