from functools import wraps

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import redirect, render
from django.http import Http404, HttpResponse
from django.views.decorators.http import require_GET, require_http_methods

from auth_module.models import ProvinceTrustee, Student, UserRole
from .forms import UserCreateForm
from .academic_imports import KINDS, import_curriculum
from .import_forms import CurriculumSpreadsheetForm
from .spreadsheets import build_spreadsheet
from .hierarchy import academic_hierarchy

User = get_user_model()


def admin_only(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not (request.user.is_superuser or request.user.role == UserRole.ADMIN):
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapped


@login_required
@admin_only
@require_http_methods(["GET", "POST"])
def curriculum_import(request, kind=None):
    if kind is not None and kind not in KINDS:
        raise Http404
    report = request.session.pop("curriculum_import_report", None)
    forms = []
    for value, (label, model) in KINDS.items():
        bound = request.method == "POST" and value == kind
        form = CurriculumSpreadsheetForm(request.POST if bound else None, request.FILES if bound else None,
                                         auto_id=f"id_{value}_%s")
        if bound and form.is_valid():
            report = import_curriculum(form.cleaned_data["file"], value, form.cleaned_data)
            request.session["curriculum_import_report"] = report[:200]
            successes = sum(item["ok"] for item in report)
            messages.info(request, f"پردازش {label}: {successes} ردیف موفق و {len(report) - successes} ردیف خطا.")
            return redirect("users_module:curriculum_import")
        forms.append({"kind": value, "label": label, "form": form})
    return render(request, "users_module/curriculum_import.html", {"import_forms": forms, "report": report})


@login_required
@admin_only
@require_GET
def curriculum_template(request, kind):
    if kind not in KINDS:
        raise Http404
    headers = ["استان", "مدرسه", "پایه"]
    if kind in {"field", "subject"}:
        headers.append("رشته")
    if kind == "subject":
        headers.append("درس")
    response = HttpResponse(build_spreadsheet(headers).getvalue(),
                            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = f'attachment; filename="fanous-{kind}-template.xlsx"'
    return response


@login_required
@admin_only
def user_create(request):
    form = UserCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            user = form.save()
            if user.role == UserRole.STUDENT:
                Student.objects.create(user=user, field=form.cleaned_data["field"])
            elif user.role == UserRole.PROVINCE_TRUSTEE:
                ProvinceTrustee.objects.create(user=user, province=form.cleaned_data["province"])
        messages.success(request, f"کاربر «{user.get_full_name() or user.username}» با موفقیت ایجاد شد.")
        return redirect("users_module:user_create")
    return render(request, "users_module/user_create.html", {"form": form, "academic_hierarchy": academic_hierarchy()})
