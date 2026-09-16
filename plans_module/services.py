from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from auth_module.models import Student, UserRole
from counseling_module.models import StudentConsultantAssignment
from users_module.models import Subject


def current_week_start(day=None):
    day = day or timezone.localdate()
    days_since_saturday = (day.weekday() + 2) % 7
    return day - timedelta(days=days_since_saturday)


def student_profile_for(user):
    return Student.objects.filter(user=user).select_related(
        "user", "field__grade__school__province"
    ).first()


def consultant_subject_ids(user):
    return set(
        Subject.objects.filter(
            Q(access__users=user) | Q(access__consultant__consultant=user),
            is_active=True,
        ).values_list("pk", flat=True)
    )


def visible_students_for(user):
    students = Student.objects.select_related("user", "field__grade__school__province")
    if user.is_superuser or user.role == UserRole.ADMIN:
        return students.filter(user__is_active=True).order_by("user__last_name", "user__first_name")
    if user.role == UserRole.CONSULTANT:
        assigned_ids = StudentConsultantAssignment.objects.filter(
            consultant=user
        ).values_list("student_id", flat=True)
        return students.filter(pk__in=assigned_ids, user__is_active=True).order_by(
            "user__last_name", "user__first_name"
        )
    return students.none()


def subjects_for_actor(user, students=None):
    queryset = Subject.objects.filter(is_active=True).select_related("field__grade")
    if user.role == UserRole.STUDENT:
        profile = student_profile_for(user)
        return queryset.filter(field=profile.field) if profile else queryset.none()
    if students:
        queryset = queryset.filter(field_id__in={student.field_id for student in students})
    return queryset.distinct().order_by("field__grade__title", "field__title", "title")


def can_manage_entry(user, entry):
    if user.is_superuser or user.role == UserRole.ADMIN:
        return True
    if user.role == UserRole.STUDENT:
        return entry.student.user_id == user.id and entry.source == "SELF"
    if user.role == UserRole.CONSULTANT:
        return entry.assigned_by_id == user.id and visible_students_for(user).filter(pk=entry.student_id).exists()
    return False
