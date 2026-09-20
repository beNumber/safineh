from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from auth_module.decorators import role_required
from auth_module.models import Student, UserRole
from questions_module.models import ExamSession
from quiz_module.models import QuizAttempt
from ticketing_module.models import (
    Ticket,
    TicketAuditLog,
    TicketMessage,
    TicketQueue,
    TicketStatus,
    TicketType,
)

from .forms import AssignmentForm, PrivateCounselingTicketForm
from .models import StudentConsultantAssignment
from .services import assignments_for_consultant, manageable_students_for, search_students


MANAGER_ROLES = (UserRole.PROVINCE_TRUSTEE, UserRole.ADMIN)


def _student_name(student):
    return student.user.get_full_name().strip() or student.user.username


@role_required(*MANAGER_ROLES)
def manage_assignments(request):
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "all")
    students = search_students(manageable_students_for(request.user), query)
    if status == "assigned":
        students = students.filter(consultant_assignment__isnull=False)
    elif status == "unassigned":
        students = students.filter(consultant_assignment__isnull=True)
    students = students.order_by("user__last_name", "user__first_name", "user__username")
    total = manageable_students_for(request.user).count()
    assigned = manageable_students_for(request.user).filter(consultant_assignment__isnull=False).count()
    consultants = (
        StudentConsultantAssignment.objects.filter(student__in=manageable_students_for(request.user))
        .values("consultant_id", "consultant__first_name", "consultant__last_name", "consultant__username")
        .annotate(student_count=Count("id"))
        .order_by("-student_count")[:6]
    )
    return render(
        request,
        "counseling_module/manage.html",
        {
            "students": students,
            "query": query,
            "status": status,
            "total_count": total,
            "assigned_count": assigned,
            "unassigned_count": total - assigned,
            "consultant_stats": consultants,
            "assignment_form": AssignmentForm(),
        },
    )


@role_required(*MANAGER_ROLES)
def assign_student(request, student_id):
    if request.method != "POST":
        raise PermissionDenied
    student = get_object_or_404(manageable_students_for(request.user), pk=student_id)
    current = StudentConsultantAssignment.objects.filter(student=student).first()
    form = AssignmentForm(request.POST, instance=current)
    if form.is_valid():
        assignment = form.save(commit=False)
        assignment.student = student
        assignment.assigned_by = request.user
        assignment.full_clean()
        assignment.save()
        messages.success(
            request,
            f"{_student_name(student)} با موفقیت به {assignment.consultant.get_full_name().strip() or assignment.consultant.username} سپرده شد.",
        )
    else:
        messages.error(request, "مشاور انتخاب‌شده معتبر نیست. دوباره تلاش کنید.")
    return redirect("counseling:manage")


@role_required(*MANAGER_ROLES)
def remove_assignment(request, student_id):
    if request.method != "POST":
        raise PermissionDenied
    student = get_object_or_404(manageable_students_for(request.user), pk=student_id)
    deleted, _ = StudentConsultantAssignment.objects.filter(student=student).delete()
    if deleted:
        messages.success(request, f"تخصیص مشاور برای {_student_name(student)} لغو شد.")
    return redirect("counseling:manage")


@role_required(UserRole.CONSULTANT)
def my_students(request):
    query = request.GET.get("q", "").strip()
    assignments = assignments_for_consultant(request.user)
    if query:
        assignments = assignments.filter(
            Q(student__user__first_name__icontains=query)
            | Q(student__user__last_name__icontains=query)
            | Q(student__user__username__icontains=query)
            | Q(student__field__title__icontains=query)
        )
    assignments = assignments.annotate(
        open_ticket_count=Count(
            "student__tickets",
            filter=Q(student__tickets__is_private_consultation=True)
            & ~Q(student__tickets__status=TicketStatus.CLOSED),
            distinct=True,
        ),
        plan_count=Count("student__plan_entries", distinct=True),
    )
    return render(
        request,
        "counseling_module/my_students.html",
        {"assignments": assignments, "query": query},
    )


def _student_exam_performance(student):
    """یک خط زمانی مشترک از آزمون‌های بانک سؤال و آزمون‌های رسمی سامانه."""
    rows = []
    bank_exams = (
        ExamSession.objects.filter(user=student.user, status=ExamSession.Status.DONE)
        .prefetch_related("chapters__subject")
        .order_by("finished_at", "started_at", "pk")
    )
    for exam in bank_exams:
        subjects = list(dict.fromkeys(chapter.subject.title for chapter in exam.chapters.all()))
        rows.append(
            {
                "kind": "bank",
                "title": "، ".join(subjects) or f"آزمون بانک سؤال #{exam.pk}",
                "percent": round(float(exam.percent or 0), 1),
                "correct": exam.correct_count,
                "wrong": exam.wrong_count,
                "unanswered": exam.unanswered_count,
                "total": exam.total_questions,
                "date": exam.finished_at or exam.started_at,
            }
        )

    official_attempts = (
        QuizAttempt.objects.filter(
            student=student.user,
            status__in=[QuizAttempt.Status.SUBMITTED, QuizAttempt.Status.GRADED],
        )
        .select_related("quiz")
        .order_by("finished_at", "started_at", "pk")
    )
    for attempt in official_attempts:
        total_questions = attempt.quiz.question_count or attempt.quiz.questions.count()
        rows.append(
            {
                "kind": "official",
                "title": attempt.quiz.title,
                "percent": round(float(attempt.percent), 1),
                "correct": attempt.correct_count,
                "wrong": attempt.wrong_count,
                "unanswered": max(total_questions - attempt.answered_count, 0),
                "total": total_questions,
                "date": attempt.finished_at or attempt.started_at,
            }
        )

    rows.sort(key=lambda item: item["date"] or timezone.now())
    for index, row in enumerate(rows, start=1):
        local_date = timezone.localtime(row["date"]) if row["date"] and timezone.is_aware(row["date"]) else row["date"]
        row["chart_label"] = f"آزمون {index}"
        row["date_label"] = local_date.strftime("%Y/%m/%d") if local_date else "—"

    completed = len(rows)
    average = round(sum(row["percent"] for row in rows) / completed, 1) if completed else 0
    best = max((row["percent"] for row in rows), default=0)
    total_questions = sum(row["total"] for row in rows)
    total_correct = sum(row["correct"] for row in rows)
    accuracy = round(total_correct * 100 / total_questions, 1) if total_questions else 0
    return rows, {
        "completed": completed,
        "average": average,
        "best": best,
        "accuracy": accuracy,
        "latest": rows[-1]["percent"] if rows else 0,
    }


@role_required(UserRole.CONSULTANT)
def student_performance(request, student_id):
    # فیلتر consultant مهم است: هیچ مشاوری به دانش‌آموز مشاور دیگر دسترسی ندارد.
    assignment = get_object_or_404(
        StudentConsultantAssignment.objects.select_related(
            "student__user", "student__field__grade", "consultant"
        ),
        student_id=student_id,
        consultant=request.user,
    )
    exams, summary = _student_exam_performance(assignment.student)
    return render(
        request,
        "counseling_module/student_performance.html",
        {"assignment": assignment, "student": assignment.student, "exams": exams, "summary": summary},
    )


@role_required(UserRole.STUDENT)
def my_consultant(request):
    student = Student.objects.filter(user=request.user).select_related(
        "field__grade__school__province"
    ).first()
    assignment = None
    tickets = Ticket.objects.none()
    if student:
        assignment = StudentConsultantAssignment.objects.filter(student=student).select_related(
            "consultant", "assigned_by"
        ).first()
        if assignment:
            tickets = Ticket.objects.filter(
                student=student,
                is_private_consultation=True,
                current_assignee_user=assignment.consultant,
            ).order_by("-updated_at")[:6]
    return render(
        request,
        "counseling_module/my_consultant.html",
        {"student": student, "assignment": assignment, "tickets": tickets},
    )


@role_required(UserRole.STUDENT)
def create_private_ticket(request):
    student = get_object_or_404(Student.objects.select_related("user"), user=request.user)
    assignment = get_object_or_404(
        StudentConsultantAssignment.objects.select_related("consultant"), student=student
    )
    form = PrivateCounselingTicketForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            ticket = Ticket.objects.create(
                title=form.cleaned_data["title"],
                student=student,
                ticket_type=TicketType.PSYCHOLOGY,
                current_queue=TicketQueue.MODERATOR,
                current_assignee_user=assignment.consultant,
                status=TicketStatus.PENDING_APPROVAL,
                is_private_consultation=True,
            )
            TicketMessage.objects.create(
                ticket=ticket,
                sender=request.user,
                content=form.cleaned_data["content"],
                attachment=form.cleaned_data.get("attachment"),
            )
            TicketAuditLog.objects.create(
                ticket=ticket,
                actor=request.user,
                action=TicketAuditLog.Action.CREATED,
                to_queue=TicketQueue.MODERATOR,
                to_user=assignment.consultant,
                description="گفت‌وگوی خصوصی در انتظار تأیید ناظر؛ مقصد نهایی مشاور اختصاصی است",
            )
        messages.success(
            request,
            "پیام ثبت شد و پس از تأیید ناظر فقط برای مشاور اختصاصی شما ارسال می‌شود.",
        )
        return redirect("ticketing:detail", pk=ticket.pk)
    return render(
        request,
        "counseling_module/private_ticket.html",
        {"form": form, "assignment": assignment},
    )
