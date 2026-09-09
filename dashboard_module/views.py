from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from auth_module.models import UserRole
from courses_module.models import ApprovalStatus, CourseEnrollment


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
    return render(request, "dashboard_module/dash.html", context)
