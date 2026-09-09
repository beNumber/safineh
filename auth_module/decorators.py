from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied


def role_required(*roles, allow_superuser=True):
    """
    دسترسی view را به نقش‌های اعلام‌شده محدود می‌کند.

    نمونه::

        @role_required(UserRole.CONSULTANT, UserRole.PROVINCE_TRUSTEE)
        def ticket_detail(request, pk):
            ...
    """

    allowed_roles = {
        getattr(role, "value", role) for role in roles
    }

    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            user = request.user
            if not user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if allow_superuser and user.is_superuser:
                return view_func(request, *args, **kwargs)
            if user.role not in allowed_roles:
                raise PermissionDenied("شما اجازه دسترسی به این بخش را ندارید.")
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator
