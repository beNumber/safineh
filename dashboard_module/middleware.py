from django.contrib import messages
from django.shortcuts import redirect
from django.db import transaction
from django.utils import timezone
from datetime import timedelta

from .models import ModuleAvailability, PresencePeak, UserPresence


class ModuleAvailabilityMiddleware:
    PREFIXES = {
        "/questions/": ModuleAvailability.Code.QUESTION_BANK,
        "/courses/": ModuleAvailability.Code.COURSES,
        "/quizzes/": ModuleAvailability.Code.QUIZZES,
        "/lessons/": ModuleAvailability.Code.COURSES,
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        is_admin = user and user.is_authenticated and (user.is_superuser or getattr(user, "role", None) == "ADMIN")
        if user and user.is_authenticated:
            now = timezone.now()
            presence, created = UserPresence.objects.get_or_create(user=user, defaults={"last_seen": now})
            if created or presence.last_seen < now - timedelta(seconds=30):
                if not created:
                    UserPresence.objects.filter(pk=presence.pk).update(last_seen=now)
                count = UserPresence.objects.filter(last_seen__gte=now - timedelta(minutes=5)).count()
                with transaction.atomic():
                    peak, _ = PresencePeak.objects.select_for_update().get_or_create(
                        day=timezone.localdate(now), defaults={"count": count, "recorded_at": now}
                    )
                    if count > peak.count:
                        peak.count = count
                        peak.recorded_at = now
                        peak.save(update_fields=["count", "recorded_at"])
        if user and user.is_authenticated and not is_admin:
            for prefix, code in self.PREFIXES.items():
                if request.path.startswith(prefix) and ModuleAvailability.objects.filter(code=code, is_active=False).exists():
                    messages.warning(request, "این بخش موقتاً توسط مدیر سامانه غیرفعال شده است.")
                    return redirect("dashboard")
        return self.get_response(request)
