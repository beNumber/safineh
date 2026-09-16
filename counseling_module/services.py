from django.db.models import Q

from auth_module.models import ProvinceTrustee, Student, UserRole

from .models import StudentConsultantAssignment


def manageable_students_for(user):
    students = Student.objects.filter(user__is_active=True).select_related(
        "user", "field__grade__school__province", "consultant_assignment__consultant"
    )
    if user.is_superuser or user.role == UserRole.ADMIN:
        return students
    if user.role == UserRole.PROVINCE_TRUSTEE:
        province_ids = ProvinceTrustee.objects.filter(user=user).values_list("province_id", flat=True)
        return students.filter(field__grade__school__province_id__in=province_ids)
    return students.none()


def assignments_for_consultant(user):
    if user.role != UserRole.CONSULTANT and not user.is_superuser:
        return StudentConsultantAssignment.objects.none()
    return StudentConsultantAssignment.objects.filter(consultant=user).select_related(
        "student__user", "student__field__grade__school__province", "assigned_by"
    )


def search_students(queryset, query):
    if not query:
        return queryset
    return queryset.filter(
        Q(user__first_name__icontains=query)
        | Q(user__last_name__icontains=query)
        | Q(user__username__icontains=query)
        | Q(user__phone_number__icontains=query)
        | Q(field__title__icontains=query)
        | Q(field__grade__title__icontains=query)
    )
