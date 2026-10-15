from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.core.models import AuditEvent

from .models import Membership, ProfessionalCredential, RoleAssignment


def get_membership(request, *, required=True):
    tenant_id = request.headers.get("X-Tenant-ID")
    memberships = Membership.objects.filter(
        user=request.user, status=Membership.Status.ACTIVE
    ).select_related("tenant")
    if tenant_id:
        membership = memberships.filter(tenant_id=tenant_id).first()
    elif memberships.count() == 1:
        membership = memberships.first()
    else:
        membership = None
    if membership is None and required:
        AuditEvent.objects.create(
            actor=request.user if request.user.is_authenticated else None,
            action="tenant.access_denied",
            metadata={"reason": "missing_or_invalid_active_tenant"},
        )
        raise PermissionDenied("Selecione uma academia ativa com o cabeçalho X-Tenant-ID.")
    return membership


def roles_for(membership):
    return set(membership.role_assignments.values_list("role", flat=True))


def require_roles(request, *allowed):
    membership = get_membership(request)
    roles = roles_for(membership)
    if not roles.intersection(allowed):
        raise PermissionDenied("Seu vínculo não permite esta operação.")
    return membership


def require_student_scope(membership, student_id, assignment_model, professional_field):
    roles = roles_for(membership)
    if RoleAssignment.Role.OWNER in roles or RoleAssignment.Role.ADMIN in roles:
        if not Membership.objects.filter(
            tenant=membership.tenant, user_id=student_id, status=Membership.Status.ACTIVE
        ).exists():
            raise PermissionDenied("Aluno fora da academia ativa.")
        return
    lookup = {
        "tenant": membership.tenant,
        professional_field: membership.user,
        "student_id": student_id,
        "is_active": True,
    }
    if not assignment_model.objects.filter(**lookup).exists():
        raise PermissionDenied("Aluno não atribuído a este profissional.")


def require_verified_dietitian(membership):
    if RoleAssignment.Role.DIETITIAN not in roles_for(membership):
        raise PermissionDenied("É necessário o papel de nutricionista.")
    credential = ProfessionalCredential.objects.filter(
        tenant=membership.tenant,
        professional=membership.user,
        kind=ProfessionalCredential.Kind.CRN,
        verified_at__isnull=False,
    ).first()
    if not credential:
        raise PermissionDenied("CRN/UF precisa estar verificado.")
    return credential


def validate_roles(role_values):
    valid = {choice for choice, _ in RoleAssignment.Role.choices}
    invalid = set(role_values) - valid
    if invalid:
        raise ValidationError({"roles": f"Papéis inválidos: {', '.join(sorted(invalid))}"})
