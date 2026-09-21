from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_POST

from auth_module.models import UserRole
from courses_module.models import ApprovalStatus, CourseEnrollment
from plans_module.models import PlanCompletion, PlanEntry
from plans_module.services import current_week_start, student_profile_for
from counseling_module.models import StudentConsultantAssignment
from counseling_module.services import manageable_students_for


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
            context["consultant_assignment"] = StudentConsultantAssignment.objects.filter(
                student=student
            ).select_related("consultant").first()
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
    elif request.user.role == UserRole.CONSULTANT:
        assignments = StudentConsultantAssignment.objects.filter(
            consultant=request.user
        ).select_related("student__user", "student__field__grade")
        context["my_students_count"] = assignments.count()
        context["recent_student_assignments"] = assignments.order_by("-updated_at")[:4]
    elif request.user.role == UserRole.PROVINCE_TRUSTEE:
        manageable = manageable_students_for(request.user)
        context["province_students_count"] = manageable.count()
        context["province_unassigned_count"] = manageable.filter(
            consultant_assignment__isnull=True
        ).count()
    if request.user.is_superuser or request.user.role == UserRole.ADMIN:
        context["all_students_count"] = manageable_students_for(request.user).count()
        context["all_unassigned_count"] = manageable_students_for(request.user).filter(
            consultant_assignment__isnull=True
        ).count()
    return render(request, "dashboard_module/dash.html", context)


@login_required
@require_POST
def mark_content_notifications_read(request):
    request.session["fanous_content_seen_at"] = timezone.now().isoformat()
    request.session.modified = True
    return JsonResponse({"ok": True})
