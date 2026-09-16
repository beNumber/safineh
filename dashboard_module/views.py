from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from auth_module.models import UserRole
from courses_module.models import ApprovalStatus, CourseEnrollment
from plans_module.models import PlanCompletion, PlanEntry
from plans_module.services import current_week_start, student_profile_for


@login_required
def dash_view(request):
    context = {}
    if request.user.role == UserRole.STUDENT:
        context["my_course_enrollments"] = CourseEnrollment.objects.filter(
            student=request.user,
            course__approval_status=ApprovalStatus.APPROVED,
            course__is_active=True,
        ).select_related("course", "course__author")[:4]
        context["my_courses_count"] = CourseEnrollment.objects.filter(student=request.user).count()
        student = student_profile_for(request.user)
        if student:
            today_index = (timezone.localdate().weekday() + 2) % 7
            today_plans = PlanEntry.objects.filter(
                student=student, weekday=today_index, is_active=True
            ).select_related("subject", "assigned_by")
            completed_ids = set(
                PlanCompletion.objects.filter(
                    entry__student=student, week_start=current_week_start()
                ).values_list("entry_id", flat=True)
            )
            context["today_plans"] = today_plans[:4]
            context["today_plans_count"] = today_plans.count()
            context["today_completed_count"] = today_plans.filter(pk__in=completed_ids).count()
    return render(request, "dashboard_module/dash.html", context)
