from auth_module.models import ProvinceTrustee, UserRole
from users_module.models import Access


def is_quiz_admin(user):
    return user.is_authenticated and (user.is_superuser or user.role == UserRole.ADMIN)


def can_create_quiz(user):
    if is_quiz_admin(user):
        return True
    return user.is_authenticated and user.role == UserRole.CONSULTANT and user.has_project_access(Access.Code.QUIZ)


def trustee_province_ids(user):
    if not user.is_authenticated or user.role != UserRole.PROVINCE_TRUSTEE:
        return []
    return list(ProvinceTrustee.objects.filter(user=user).values_list("province_id", flat=True))


def can_manage_quiz(user, quiz):
    if is_quiz_admin(user):
        return True
    return can_create_quiz(user) and quiz.creator_id == user.id and quiz.status in {quiz.Status.DRAFT, quiz.Status.REJECTED}


def can_review_quiz(user, quiz):
    if is_quiz_admin(user):
        return True
    return quiz.province_id in trustee_province_ids(user)


def can_view_results(user, quiz):
    return is_quiz_admin(user) or quiz.creator_id == user.id or can_review_quiz(user, quiz)
