import uuid
from collections import defaultdict
from datetime import date, timedelta

import jdatetime

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from auth_module.decorators import role_required
from auth_module.models import UserRole

from .forms import PlanEntryForm, StaffPlanEntryForm
from .models import ActivityType, PlanCompletion, PlanEntry, PlanSource
from .services import (
    can_manage_entry,
    current_week_start,
    student_profile_for,
    subjects_for_actor,
    visible_students_for,
)


ALLOWED_ROLES = (UserRole.STUDENT, UserRole.CONSULTANT, UserRole.ADMIN)


def _source_for(user):
    if user.is_superuser or user.role == UserRole.ADMIN:
        return PlanSource.ADMIN
    if user.role == UserRole.CONSULTANT:
        return PlanSource.CONSULTANT
    return PlanSource.SELF


def _entry_payload(cleaned, student, actor, batch_id=None):
    return PlanEntry(
        student=student,
        subject=cleaned.get("subject"),
        activity_type=cleaned["activity_type"],
        title=cleaned.get("title", ""),
        scheduled_date=cleaned["scheduled_date"],
        weekday=(cleaned["scheduled_date"].weekday() + 2) % 7,
        start_hour=cleaned["start_hour"],
        end_hour=cleaned["end_hour"],
        color=cleaned["color"],
        notes=cleaned.get("notes", ""),
        source=_source_for(actor),
        assigned_by=actor,
        batch_id=batch_id,
    )


PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
JALALI_MONTHS = (
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
)
JALALI_WEEKDAYS = (
    "شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه",
)


def _selected_week(request):
    requested = request.GET.get("week")
    if requested:
        try:
            return current_week_start(date.fromisoformat(requested))
        except ValueError:
            pass
    return current_week_start()


def _board_context(student, week_start):
    entries = list(
        PlanEntry.objects.filter(
            student=student,
            is_active=True,
            scheduled_date__range=(week_start, week_start + timedelta(days=5)),
        ).select_related(
            "subject", "assigned_by"
        )
    )
    completed_ids = set(
        PlanCompletion.objects.filter(entry__student=student, week_start=week_start).values_list(
            "entry_id", flat=True
        )
    )
    grouped = defaultdict(list)
    total_hours = 0
    completed_count = 0
    for entry in entries:
        entry.start_column = entry.start_hour - 8 + 2
        entry.end_column = entry.end_hour - 8 + 2
        entry.is_completed_this_week = entry.pk in completed_ids
        grouped[entry.weekday].append(entry)
        total_hours += entry.duration
        completed_count += int(entry.is_completed_this_week)

    today = timezone.localdate()
    calendar_days = []
    for value, label in enumerate(JALALI_WEEKDAYS):
        gregorian_date = week_start + timedelta(days=value)
        jalali_date = jdatetime.date.fromgregorian(date=gregorian_date)
        calendar_days.append(
            {
                "value": value,
                "label": label,
                "date": gregorian_date,
                "jalali_day": str(jalali_date.day).translate(PERSIAN_DIGITS),
                "jalali_month": JALALI_MONTHS[jalali_date.month - 1],
                "jalali_full": jalali_date.strftime("%Y/%m/%d").translate(PERSIAN_DIGITS),
                "grid_row": value + 2,
                "entries": grouped[value],
                "is_today": gregorian_date == today,
                "is_friday": value == 6,
            }
        )
    days = calendar_days[:6]
    first_jalali = jdatetime.date.fromgregorian(date=week_start)
    last_jalali = jdatetime.date.fromgregorian(date=week_start + timedelta(days=6))
    if first_jalali.month == last_jalali.month:
        month_title = f"{JALALI_MONTHS[first_jalali.month - 1]} {first_jalali.year}"
        week_range_title = (
            f"{first_jalali.day} تا {last_jalali.day} "
            f"{JALALI_MONTHS[first_jalali.month - 1]} {first_jalali.year}"
        )
    else:
        month_title = (
            f"{JALALI_MONTHS[first_jalali.month - 1]} تا "
            f"{JALALI_MONTHS[last_jalali.month - 1]} {last_jalali.year}"
        )
        week_range_title = (
            f"{first_jalali.day} {JALALI_MONTHS[first_jalali.month - 1]} تا "
            f"{last_jalali.day} {JALALI_MONTHS[last_jalali.month - 1]} {last_jalali.year}"
        )
    return {
        "board_days": days,
        "calendar_days": calendar_days,
        "hours": range(8, 25),
        "slot_hours": range(8, 24),
        "week_start": week_start,
        "week_start_jalali": first_jalali.strftime("%Y/%m/%d").translate(PERSIAN_DIGITS),
        "week_month_title": month_title.translate(PERSIAN_DIGITS),
        "week_range_title": week_range_title.translate(PERSIAN_DIGITS),
        "is_current_week": week_start == current_week_start(today),
        "previous_week": (week_start - timedelta(days=7)).isoformat(),
        "next_week": (week_start + timedelta(days=7)).isoformat(),
        "current_week": current_week_start().isoformat(),
        "total_entries": len(entries),
        "total_hours": total_hours,
        "completed_count": completed_count,
        "completion_percent": round(completed_count * 100 / len(entries)) if entries else 0,
    }


@role_required(*ALLOWED_ROLES)
def plan_board(request):
    is_student = request.user.role == UserRole.STUDENT and not request.user.is_superuser
    visible_students = None
    selected_student = None
    search_query = request.GET.get("q", "").strip()
    selected_week = _selected_week(request)

    if is_student:
        selected_student = student_profile_for(request.user)
        if not selected_student:
            messages.error(request, "پروفایل دانش‌آموزی شما کامل نشده است.")
    else:
        visible_students = visible_students_for(request.user)
        if search_query:
            visible_students = visible_students.filter(
                Q(user__first_name__icontains=search_query)
                | Q(user__last_name__icontains=search_query)
                | Q(user__username__icontains=search_query)
                | Q(field__title__icontains=search_query)
                | Q(field__grade__title__icontains=search_query)
            )
        selected_id = request.GET.get("student")
        if selected_id:
            selected_student = get_object_or_404(visible_students, pk=selected_id)
        else:
            selected_student = visible_students.first()

    if is_student:
        available_subjects = subjects_for_actor(request.user)
        form = PlanEntryForm(
            request.POST or None,
            actor=request.user,
            subjects=available_subjects,
            initial={"scheduled_date": jdatetime.date.fromgregorian(date=selected_week).strftime("%Y/%m/%d").translate(PERSIAN_DIGITS), "color": "blue"},
        )
    else:
        all_visible_students = visible_students_for(request.user)
        available_subjects = subjects_for_actor(request.user)
        initial_targets = [selected_student.pk] if selected_student else []
        form_data = request.POST.copy() if request.method == "POST" else None
        if form_data is not None and not form_data.getlist("target_students"):
            snapshot_ids = [
                value for value in form_data.get("selection_snapshot", "").split(",") if value.isdigit()
            ]
            if snapshot_ids:
                form_data.setlist("target_students", snapshot_ids)
            elif selected_student:
                form_data.setlist("target_students", [str(selected_student.pk)])
        form = StaffPlanEntryForm(
            form_data,
            actor=request.user,
            subjects=available_subjects,
            students=all_visible_students,
            initial={"target_students": initial_targets, "scheduled_date": jdatetime.date.fromgregorian(date=selected_week).strftime("%Y/%m/%d").translate(PERSIAN_DIGITS), "color": "violet"},
        )

    if request.method == "POST" and form.is_valid():
        if is_student:
            targets = [selected_student] if selected_student else []
        elif form.cleaned_data.get("apply_to_all"):
            targets = list(visible_students_for(request.user))
        else:
            targets = list(form.cleaned_data["target_students"])

        subject = form.cleaned_data.get("subject")
        invalid_targets = [student for student in targets if subject and subject.field_id != student.field_id]
        if invalid_targets:
            form.add_error(
                "subject",
                "درس انتخاب‌شده باید برای رشته همه دانش‌آموزان هدف تعریف شده باشد.",
            )
        elif not targets:
            form.add_error(None, "دانش‌آموزی برای ثبت برنامه پیدا نشد.")
        else:
            batch_id = uuid.uuid4() if len(targets) > 1 else None
            try:
                with transaction.atomic():
                    for student in targets:
                        entry = _entry_payload(form.cleaned_data, student, request.user, batch_id)
                        entry.full_clean()
                        entry.save()
            except ValidationError as error:
                form.add_error(None, "; ".join(error.messages))
            else:
                messages.success(request, f"برنامه با موفقیت برای {len(targets)} دانش‌آموز ثبت شد.")
                destination = reverse("plans_module:board")
                focus_student = targets[0] if targets else selected_student
                destination += f"?week={current_week_start(form.cleaned_data['scheduled_date']).isoformat()}"
                if not is_student and focus_student:
                    destination += f"&student={focus_student.pk}"
                return redirect(destination)

    context = {
        "form": form,
        "selected_student": selected_student,
        "visible_students": visible_students,
        "search_query": search_query,
        "is_student_view": is_student,
        "activity_types": ActivityType,
    }
    if selected_student:
        context.update(_board_context(selected_student, selected_week))
    return render(request, "plans_module/board.html", context)


@role_required(*ALLOWED_ROLES)
def plan_edit(request, pk):
    entry = get_object_or_404(
        PlanEntry.objects.select_related("student__user", "student__field", "subject", "assigned_by"), pk=pk
    )
    if not can_manage_entry(request.user, entry):
        raise PermissionDenied("اجازه ویرایش این برنامه را ندارید.")
    subjects = subjects_for_actor(request.user, [entry.student]).filter(field=entry.student.field)
    initial = {
        "activity_type": entry.activity_type,
        "subject": entry.subject_id,
        "title": entry.title,
        "scheduled_date": jdatetime.date.fromgregorian(date=entry.scheduled_date).strftime("%Y/%m/%d").translate(PERSIAN_DIGITS),
        "start_hour": entry.start_hour,
        "end_hour": entry.end_hour,
        "color": entry.color,
        "notes": entry.notes,
    }
    form = PlanEntryForm(request.POST or None, actor=request.user, subjects=subjects, initial=initial)
    if request.method == "POST" and form.is_valid():
        for field in ("activity_type", "subject", "title", "scheduled_date", "start_hour", "end_hour", "color", "notes"):
            setattr(entry, field, form.cleaned_data.get(field))
        try:
            entry.full_clean()
        except ValidationError as error:
            form.add_error(None, "; ".join(error.messages))
        else:
            entry.save()
            messages.success(request, "برنامه ویرایش شد.")
            url = f"{reverse('plans_module:board')}?week={current_week_start(entry.scheduled_date).isoformat()}"
            if request.user.role != UserRole.STUDENT or request.user.is_superuser:
                url += f"&student={entry.student_id}"
            return redirect(url)
    return render(request, "plans_module/edit.html", {"form": form, "entry": entry})


@role_required(*ALLOWED_ROLES)
def plan_delete(request, pk):
    if request.method != "POST":
        raise PermissionDenied
    entry = get_object_or_404(PlanEntry.objects.select_related("student__user"), pk=pk)
    if not can_manage_entry(request.user, entry):
        raise PermissionDenied("اجازه حذف این برنامه را ندارید.")
    student_id = entry.student_id
    entry.delete()
    messages.success(request, "آیتم برنامه حذف شد.")
    url = reverse("plans_module:board")
    if request.user.role != UserRole.STUDENT or request.user.is_superuser:
        url += f"?student={student_id}"
    return redirect(url)


@role_required(UserRole.STUDENT)
def toggle_completion(request, pk):
    if request.method != "POST":
        raise PermissionDenied
    entry = get_object_or_404(PlanEntry, pk=pk, student__user=request.user, is_active=True)
    try:
        requested_week = date.fromisoformat(request.POST.get("week_start", ""))
    except ValueError:
        requested_week = timezone.localdate()
    week_start = current_week_start(requested_week)
    completion, created = PlanCompletion.objects.get_or_create(entry=entry, week_start=week_start)
    if not created:
        completion.delete()
    completed = created
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"completed": completed, "entry_id": entry.pk})
    messages.success(request, "وضعیت انجام برنامه به‌روزرسانی شد.")
    return redirect(f"{reverse('plans_module:board')}?week={week_start.isoformat()}")
