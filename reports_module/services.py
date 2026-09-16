from dataclasses import dataclass
from datetime import timedelta

from django.db.models import Count, ExpressionWrapper, F, IntegerField, OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from auth_module.models import User, UserRole
from counseling_module.models import StudentConsultantAssignment
from courses_module.models import Course, CourseEnrollment
from plans_module.models import PlanCompletion, PlanEntry
from questions_module.models import ExamAnswer, ExamSession, PracticeAnswer, PracticeSession, Question
from ticketing_module.models import Ticket, TicketMessage


@dataclass(frozen=True)
class ReportPeriod:
    key: str
    label: str
    days: int | None

    @property
    def start(self):
        if self.days is None:
            return None
        return timezone.now() - timedelta(days=self.days)


PERIODS = (
    ReportPeriod("7", "۷ روز اخیر", 7),
    ReportPeriod("30", "۳۰ روز اخیر", 30),
    ReportPeriod("90", "۳ ماه اخیر", 90),
    ReportPeriod("365", "یک سال اخیر", 365),
    ReportPeriod("all", "از ابتدا", None),
)
PERIOD_MAP = {period.key: period for period in PERIODS}

ROLE_REPORTS = {
    "consultants": {
        "role": UserRole.CONSULTANT,
        "label": "مشاوران",
        "singular": "مشاور",
        "description": "دوره‌ها، پاسخ‌ها، سؤالات و برنامه‌های ثبت‌شده",
        "icon": "fa-user-tie",
        "accent": "violet",
    },
    "trustees": {
        "role": UserRole.PROVINCE_TRUSTEE,
        "label": "معتمدان استانی",
        "singular": "معتمد استان",
        "description": "بررسی محتوا، تخصیص‌ها و پاسخ‌گویی استانی",
        "icon": "fa-building-shield",
        "accent": "cyan",
    },
    "students": {
        "role": UserRole.STUDENT,
        "label": "دانش‌آموزان",
        "singular": "دانش‌آموز",
        "description": "یادگیری، آزمون‌ها، تیکت‌ها و انجام برنامه",
        "icon": "fa-user-graduate",
        "accent": "emerald",
    },
}


def _count_subquery(model, owner_field, start=None, date_field=None):
    filters = {owner_field: OuterRef("pk")}
    if start is not None and date_field:
        filters[f"{date_field}__gte"] = start
    queryset = model.objects.filter(**filters)
    group_field = owner_field.removesuffix("_id")
    return Coalesce(
        Subquery(
            queryset.order_by().values(group_field).annotate(total=Count("pk")).values("total")[:1],
            output_field=IntegerField(),
        ),
        Value(0),
    )


def _consultant_queryset(start):
    queryset = User.objects.filter(role=UserRole.CONSULTANT, is_superuser=False).annotate(
        courses_count=_count_subquery(Course, "author_id", start, "created_at"),
        replies_count=_count_subquery(TicketMessage, "sender_id", start, "created_at"),
        questions_count=_count_subquery(Question, "creator_id", start, "created_at"),
        plans_count=_count_subquery(PlanEntry, "assigned_by_id", start, "created_at"),
        students_count=_count_subquery(StudentConsultantAssignment, "consultant_id"),
    )
    queryset = queryset.annotate(
        activity_score=ExpressionWrapper(
            F("courses_count") + F("replies_count") + F("questions_count") + F("plans_count"),
            output_field=IntegerField(),
        )
    )
    metrics = (
        ("courses_count", "دوره ساخته", "fa-circle-play"),
        ("replies_count", "پاسخ تیکت", "fa-reply"),
        ("questions_count", "سؤال ثبت‌شده", "fa-circle-question"),
        ("plans_count", "برنامه چیده‌شده", "fa-calendar-check"),
        ("students_count", "دانش‌آموز فعلی", "fa-users"),
    )
    return queryset, metrics


def _trustee_queryset(start):
    queryset = User.objects.filter(role=UserRole.PROVINCE_TRUSTEE, is_superuser=False).annotate(
        course_reviews_count=_count_subquery(Course, "reviewed_by_id", start, "reviewed_at"),
        message_reviews_count=_count_subquery(TicketMessage, "reviewed_by_id", start, "reviewed_at"),
        assignments_count=_count_subquery(StudentConsultantAssignment, "assigned_by_id", start, "created_at"),
        replies_count=_count_subquery(TicketMessage, "sender_id", start, "created_at"),
        question_reviews_count=_count_subquery(Question, "approved_by_id", start, "approved_at"),
    )
    queryset = queryset.annotate(
        activity_score=ExpressionWrapper(
            F("course_reviews_count") + F("message_reviews_count") + F("assignments_count")
            + F("replies_count") + F("question_reviews_count"),
            output_field=IntegerField(),
        )
    )
    metrics = (
        ("course_reviews_count", "بررسی دوره", "fa-shield-check"),
        ("message_reviews_count", "بررسی پیام", "fa-shield-halved"),
        ("assignments_count", "تخصیص مشاور", "fa-people-arrows-left-right"),
        ("replies_count", "پاسخ تیکت", "fa-reply"),
        ("question_reviews_count", "بررسی سؤال", "fa-circle-check"),
    )
    return queryset, metrics


def _student_queryset(start):
    queryset = User.objects.filter(role=UserRole.STUDENT, is_superuser=False).annotate(
        enrollments_count=_count_subquery(CourseEnrollment, "student_id", start, "created_at"),
        tickets_count=_count_subquery(Ticket, "student__user_id", start, "created_at"),
        replies_count=_count_subquery(TicketMessage, "sender_id", start, "created_at"),
        practice_count=_count_subquery(PracticeSession, "user_id", start, "started_at"),
        exam_count=_count_subquery(ExamSession, "user_id", start, "started_at"),
        answers_count=ExpressionWrapper(
            _count_subquery(PracticeAnswer, "session__user_id", start, "answered_at")
            + _count_subquery(ExamAnswer, "session__user_id", start, "answered_at"),
            output_field=IntegerField(),
        ),
        completions_count=_count_subquery(PlanCompletion, "entry__student__user_id", start, "completed_at"),
    )
    queryset = queryset.annotate(
        activity_score=ExpressionWrapper(
            F("enrollments_count") + F("tickets_count") + F("replies_count") + F("practice_count")
            + F("exam_count") + F("answers_count") + F("completions_count"),
            output_field=IntegerField(),
        )
    )
    metrics = (
        ("answers_count", "پاسخ ثبت‌شده", "fa-pen-to-square"),
        ("practice_count", "جلسه تمرین", "fa-dumbbell"),
        ("exam_count", "آزمون", "fa-file-circle-check"),
        ("completions_count", "برنامه انجام‌شده", "fa-list-check"),
        ("enrollments_count", "عضویت در دوره", "fa-graduation-cap"),
        ("tickets_count", "تیکت ساخته", "fa-ticket"),
    )
    return queryset, metrics


def activity_queryset(section, period):
    builders = {
        "consultants": _consultant_queryset,
        "trustees": _trustee_queryset,
        "students": _student_queryset,
    }
    return builders[section](period.start)


def apply_people_filters(queryset, query, state):
    if query:
        queryset = queryset.filter(
            Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(username__icontains=query)
            | Q(phone_number__icontains=query)
        )
    if state == "active":
        queryset = queryset.filter(is_active=True)
    elif state == "inactive":
        queryset = queryset.filter(is_active=False)
    return queryset


def apply_order(queryset, order):
    ordering = {
        "recent": (F("last_login").desc(nulls_last=True), "last_name", "first_name"),
        "name": ("last_name", "first_name", "username"),
        "quiet": ("activity_score", "last_name", "first_name"),
    }
    return queryset.order_by(*ordering.get(order, ("-activity_score", "last_name", "first_name")))


def user_context(user, metric_definitions, section):
    user.report_metrics = [
        {"value": getattr(user, field), "label": label, "icon": icon}
        for field, label, icon in metric_definitions
    ]
    user.display_name = user.get_full_name().strip() or user.username
    user.initial = user.display_name[:1]
    user.context_label = "اطلاعات تکمیلی ثبت نشده"
    if section == "students":
        profile = next(iter(user.student_profiles.all()), None)
        if profile:
            user.context_label = f"{profile.field.title} · {profile.province}"
    elif section == "trustees":
        provinces = [str(item.province) for item in user.trustee_provinces.all()]
        if provinces:
            user.context_label = "، ".join(provinces)
    else:
        access_labels = [str(access) for access in user.accesses.all()]
        if access_labels:
            user.context_label = f"{len(access_labels)} دسترسی تخصصی"
    return user
