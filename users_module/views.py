from functools import wraps

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import redirect, render

from auth_module.models import ProvinceTrustee, Student, UserRole
from .forms import UserCreateForm

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
    return render(request, "users_module/user_create.html", {"form": form})
