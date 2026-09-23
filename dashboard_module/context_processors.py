from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from auth_module.models import UserRole
from blog_module.models import Post
from news_module.models import Article
from classroom_module.models import OnlineClass


ROLE_COPY = {
    UserRole.STUDENT: ("دانش‌آموز پرتلاش فانوس", "امروز هم یک فرصت تازه برای نزدیک‌تر شدن به هدفت داری."),
    UserRole.CONSULTANT: ("مشاور همراه فانوس", "حضور تو می‌تواند مسیر یک دانش‌آموز را روشن‌تر کند."),
    UserRole.PROVINCE_TRUSTEE: ("مسئول منطقه فانوس", "مدیریت مسیر آموزشی منطقه امروز در دستان توست."),
    UserRole.CONTENT_MODERATOR: ("ناظر محتوای فانوس", "کیفیت هر محتوا، روشنایی مسیر یادگیری را بیشتر می‌کند."),
    UserRole.ADMIN: ("مدیر فانوس", "امروز هم مرکز کنترل سامانه آماده تصمیم‌های دقیق توست."),
}


def _day_greeting():
    hour = timezone.localtime().hour
    if hour < 12:
        return "صبح روشن بخیر"
    if hour < 17:
        return "ظهر دل‌انگیز بخیر"
    if hour < 21:
        return "عصر پرانرژی بخیر"
    return "شب آرام بخیر"


def fanous_shell(request):
    if not request.user.is_authenticated:
        return {}

    now = timezone.now()
    raw_last_seen = request.session.get("fanous_content_seen_at")
    last_seen = parse_datetime(raw_last_seen) if raw_last_seen else None
    if last_seen is None:
        last_seen = now - timedelta(days=7)
    if timezone.is_naive(last_seen):
        last_seen = timezone.make_aware(last_seen)

    posts = list(
        Post.published.filter(published_at__gt=last_seen)
        .only("title", "slug", "published_at")[:6]
    )
    articles = list(
        Article.objects.filter(
            status=Article.Status.PUBLISHED,
            published_at__lte=now,
            published_at__gt=last_seen,
        ).only("title", "slug", "published_at")[:6]
    )
    items = [
        {
            "kind": "blog",
            "title": item.title,
            "published_at": item.published_at,
            "url": reverse("blog:post_detail", kwargs={"slug": item.slug}),
        }
        for item in posts
    ] + [
        {
            "kind": "news",
            "title": item.title,
            "published_at": item.published_at,
            "url": reverse("news_module:article_detail", kwargs={"slug": item.slug}),
        }
        for item in articles
    ]
    items.sort(key=lambda item: item["published_at"], reverse=True)

    class_items = []
    has_class_indicator = False
    if request.user.role in (UserRole.STUDENT, UserRole.CONSULTANT) or request.user.is_superuser or request.user.role == UserRole.ADMIN:
        local_now = timezone.localtime(now)
        tomorrow = now + timedelta(hours=24)
        upcoming_classes = OnlineClass.objects.filter(is_active=True, starts_at__lte=tomorrow, ends_at__gte=now).order_by("starts_at")[:4]
        has_class_indicator = OnlineClass.objects.filter(is_active=True, starts_at__date=local_now.date()).exists()
        class_items = [{"kind": "classroom", "title": f"کلاس: {item.title}", "published_at": item.starts_at, "url": reverse("classroom_module:list")} for item in upcoming_classes]
        items = class_items + items

    role_title, role_message = ROLE_COPY.get(
        request.user.role,
        ("همراه فانوس", "هر قدم کوچک امروز، بخشی از یک مسیر روشن‌تر است."),
    )
    if request.user.is_superuser:
        role_title, role_message = ROLE_COPY[UserRole.ADMIN]

    return {
        "fanous_day_greeting": _day_greeting(),
        "fanous_role_title": role_title,
        "fanous_role_message": role_message,
        "fanous_notifications": items[:6],
        "fanous_unread_count": len(items),
        "fanous_has_class": has_class_indicator,
    }
