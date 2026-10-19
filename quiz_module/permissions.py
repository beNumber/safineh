from auth_module.models import ProvinceTrustee, UserRole
from users_module.models import Access
from django.db.models import CharField, Count, Exists, ExpressionWrapper, F, IntegerField, OuterRef, Q
from django.utils import timezone


def student_quizzes(user, queryset=None):
    from .models import Quiz

    quizzes = queryset if queryset is not None else Quiz.objects.all()
    if not user.is_authenticated or user.role != UserRole.STUDENT or user.is_superuser:
        return quizzes.none()
    profiles = user.student_profiles.annotate(
        target_field=ExpressionWrapper(OuterRef("field__title"), output_field=CharField()),
        target_grade=ExpressionWrapper(OuterRef("grade__title"), output_field=CharField()),
        target_school=ExpressionWrapper(OuterRef("school_id"), output_field=IntegerField()),
        target_province=ExpressionWrapper(OuterRef("province_id"), output_field=IntegerField()),
    ).filter(
        Q(target_field__isnull=True) | Q(field__title=F("target_field")),
        Q(target_grade__isnull=True) | Q(field__grade__title=F("target_grade")),
        Q(target_school__isnull=True) | Q(field__grade__school_id=F("target_school")),
        Q(target_province__isnull=True) | Q(field__grade__school__province_id=F("target_province")),
    )
    quizzes = quizzes.alias(matches_student_profile=Exists(profiles))
    audience = Q(all_students=True) | Q(assigned_students=user)
    audience |= Q(assigned_students__isnull=True, matches_student_profile=True)
    return quizzes.filter(status=Quiz.Status.APPROVED).filter(audience).distinct()


def available_student_quizzes(user, now=None):
    from .models import QuizAttempt

    now = now or timezone.now()
    live_attempt = QuizAttempt.objects.filter(
        quiz_id=OuterRef("pk"), student=user, status=QuizAttempt.Status.IN_PROGRESS,
    ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
    return student_quizzes(user).filter(is_paused=False, closes_at__gt=now).annotate(
        own_attempt_count=Count("attempts", filter=Q(attempts__student=user), distinct=True),
        has_live_attempt=Exists(live_attempt),
    ).filter(Q(own_attempt_count__lt=F("max_attempts")) | Q(has_live_attempt=True)).order_by("opens_at", "pk")


def is_quiz_admin(user):
    return user.is_authenticated and (user.is_superuser or user.role == UserRole.ADMIN)


def can_create_quiz(user):
    if is_quiz_admin(user):
        return True
    return user.is_authenticated and user.is_active and user.role == UserRole.CONSULTANT and (
        user.has_project_access(Access.Code.QUIZ)
        or user.scopes.filter(accesses__name=Access.Code.QUIZ).exists()
        or user.counseling_assignments.exists()
    )


def has_full_quiz_access(user):
    return is_quiz_admin(user) or (
        user.is_authenticated and user.role == UserRole.CONSULTANT and (
            user.has_project_access(Access.Code.QUIZ)
            or user.scopes.filter(accesses__name=Access.Code.QUIZ).exists()
        )
    )


def quiz_students_for(user):
    from django.contrib.auth import get_user_model

    students = get_user_model().objects.filter(role=UserRole.STUDENT, is_active=True)
    if not has_full_quiz_access(user):
        students = students.filter(student_profiles__consultant_assignment__consultant=user)
    return students.distinct()


def trustee_province_ids(user):
    if not user.is_authenticated or user.role != UserRole.PROVINCE_TRUSTEE:
        return []
    return list(ProvinceTrustee.objects.filter(user=user).values_list("province_id", flat=True))


def can_manage_quiz(user, quiz):
    if is_quiz_admin(user):
        return True
    return can_create_quiz(user) and quiz.creator_id == user.id


def can_edit_quiz_questions(user, quiz):
    """Question editing is also available to the trustee of an approved quiz."""
    if can_manage_quiz(user, quiz):
        return True
    return (
        user.is_authenticated
        and user.role == UserRole.PROVINCE_TRUSTEE
        and quiz.status == quiz.Status.APPROVED
        and quiz.province_id in trustee_province_ids(user)
    )


def can_review_quiz(user, quiz):
    if is_quiz_admin(user):
        return True
    return quiz.province_id in trustee_province_ids(user)


def can_view_results(user, quiz):
    return is_quiz_admin(user) or quiz.creator_id == user.id or can_review_quiz(user, quiz)
