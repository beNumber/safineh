from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from auth_module.models import UserRole
from .forms import OnlineClassForm
from .models import OnlineClass


def _is_admin(user):
    return user.is_superuser or user.role == UserRole.ADMIN


@login_required
def class_list(request):
    if not (_is_admin(request.user) or request.user.role in (UserRole.STUDENT, UserRole.CONSULTANT)):
        raise PermissionDenied
    classes = OnlineClass.objects.filter(is_active=True) if not _is_admin(request.user) else OnlineClass.objects.all()
    return render(request, "classroom_module/class_list.html", {"classes": classes, "now": timezone.now(), "can_manage": _is_admin(request.user)})


@login_required
def class_form(request, pk=None):
    if not _is_admin(request.user):
        raise PermissionDenied
    instance = get_object_or_404(OnlineClass, pk=pk) if pk else None
    form = OnlineClassForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        if not item.created_by_id:
            item.created_by = request.user
        item.save()
        messages.success(request, "کلاس با موفقیت ذخیره شد.")
        return redirect("classroom_module:list")
    return render(request, "classroom_module/class_form.html", {"form": form, "item": instance})


@login_required
@require_POST
def class_delete(request, pk):
    if not _is_admin(request.user):
        raise PermissionDenied
    get_object_or_404(OnlineClass, pk=pk).delete()
    messages.success(request, "کلاس حذف شد.")
    return redirect("classroom_module:list")
