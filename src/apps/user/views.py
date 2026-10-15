from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from apps.core.models import AuditEvent
from apps.tenancy.models import Membership, RoleAssignment
from apps.tenancy.services import get_membership, require_roles

from .serializers import (
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    UserSerializer,
)

User = get_user_model()


def send_reset(user, *, actor=None, tenant=None):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    send_mail(
        "Redefinição de senha — Bota o Shape",
        f"Use este código para redefinir sua senha: {uid}:{token}",
        None,
        [user.email],
    )
    AuditEvent.objects.create(
        tenant=tenant, actor=actor, action="password_reset.requested", target_id=str(user.pk)
    )


class PasswordResetRequestView(GenericAPIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    serializer_class = PasswordResetRequestSerializer

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.filter(
            email__iexact=serializer.validated_data["email"], is_active=True
        ).first()
        if user:
            send_reset(user)
        return Response({"detail": "Se a conta existir, enviaremos as instruções."})


class PasswordResetConfirmView(GenericAPIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    serializer_class = PasswordResetConfirmSerializer

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        AuditEvent.objects.create(
            actor=user, action="password_reset.completed", target_id=str(user.pk)
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class UserViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin, GenericViewSet
):
    serializer_class = UserSerializer
    queryset = User.objects.all()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return self.queryset.none()
        membership = get_membership(self.request)
        roles = set(membership.role_assignments.values_list("role", flat=True))
        if roles.intersection({RoleAssignment.Role.OWNER, RoleAssignment.Role.ADMIN}):
            user_ids = Membership.objects.filter(tenant=membership.tenant).values("user_id")
            return User.objects.filter(id__in=user_ids).order_by("first_name", "email")
        return User.objects.filter(pk=self.request.user.pk)

    def perform_update(self, serializer):
        target = self.get_object()
        if target != self.request.user:
            require_roles(self.request, RoleAssignment.Role.OWNER, RoleAssignment.Role.ADMIN)
        serializer.save()

    @action(detail=True, methods=["post"])
    def request_password_reset(self, request, pk=None):
        membership = require_roles(request, RoleAssignment.Role.OWNER, RoleAssignment.Role.ADMIN)
        target = self.get_object()
        send_reset(target, actor=request.user, tenant=membership.tenant)
        return Response(status=status.HTTP_204_NO_CONTENT)
