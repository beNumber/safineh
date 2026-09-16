from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Sum
from django.shortcuts import render
from django.utils import timezone

from auth_module.models import UserRole

from .services import (
    PERIOD_MAP,
    PERIODS,
    ROLE_REPORTS,
    activity_queryset,
    apply_order,
    apply_people_filters,
    user_context,
)


@login_required
def people_activity(request):
    if not (request.user.is_superuser or request.user.role == UserRole.ADMIN):
        raise PermissionDenied("این گزارش فقط برای مدیر کل سامانه در دسترس است.")

    section = request.GET.get("section", "consultants")
    if section not in ROLE_REPORTS:
        section = "consultants"
    period = PERIOD_MAP.get(request.GET.get("period", "30"), PERIOD_MAP["30"])
    query = request.GET.get("q", "").strip()[:100]
    state = request.GET.get("state", "all")
    order = request.GET.get("order", "activity")

    queryset, metric_definitions = activity_queryset(section, period)
    queryset = queryset.prefetch_related(
        "accesses",
        "student_profiles__field__grade__school__province",
        "trustee_provinces__province",
    )
    queryset = apply_people_filters(queryset, query, state)

    summary_result = queryset.aggregate(total_activity=Sum("activity_score"))
    total_people = queryset.count()
    active_people = queryset.filter(is_active=True).count()
    if period.start:
        logged_in_period = queryset.filter(last_login__gte=period.start).count()
    else:
        logged_in_period = queryset.filter(last_login__isnull=False).count()

    paginator = Paginator(apply_order(queryset, order), 12)
    page_obj = paginator.get_page(request.GET.get("page"))
    page_obj.object_list = [
        user_context(user, metric_definitions, section) for user in page_obj.object_list
    ]

    context = {
        "sections": ROLE_REPORTS,
        "active_section": section,
        "section_meta": ROLE_REPORTS[section],
        "periods": PERIODS,
        "active_period": period,
        "query": query,
        "state": state,
        "order": order,
        "page_obj": page_obj,
        "summary": {
            "people": total_people,
            "active": active_people,
            "logged_in": logged_in_period,
            "activity": summary_result["total_activity"] or 0,
        },
        "generated_at": timezone.now(),
    }
    return render(request, "reports_module/people_activity.html", context)
