from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import ArticleForm, CategoryForm, TagForm
from .models import Article, Category, Tag

# ---------------------------------------------------------------
# ابزار کمکی (دسترسی مدیریت)
# ---------------------------------------------------------------

def _is_staff(user):
    return user.is_authenticated and user.is_staff


def _require_staff(user):
    """برای سازگاری با کدهای قبلی نگه داشته شده است."""
    return _is_staff(user)


# ---------------------------------------------------------------
# نمایش عمومی
# ---------------------------------------------------------------

def article_list(request):
    """لیست اخبار منتشرشده (با فیلتر دسته و تگ و جستجو)"""
    articles = Article.objects.filter(
        status=Article.Status.PUBLISHED,
        published_at__lte=timezone.now(),
    ).select_related("category", "author").prefetch_related("tags")

    category_slug = request.GET.get("category")
    tag_slug = request.GET.get("tag")
    query = request.GET.get("q")

    if category_slug:
        articles = articles.filter(category__slug=category_slug)
    if tag_slug:
        articles = articles.filter(tags__slug=tag_slug)
    if query:
        articles = articles.filter(
            Q(title__icontains=query)
            | Q(summary__icontains=query)
            | Q(content__icontains=query)
        )

    categories = Category.objects.filter(is_active=True)
    tags = Tag.objects.all()

    paginator = Paginator(articles, 9)  # ۹ خبر در هر صفحه
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "categories": categories,
        "tags": tags,
        "current_category": category_slug,
        "current_tag": tag_slug,
        "query": query,
    }
    return render(request, "news_modal/article_list.html", context)


def article_detail(request, slug):
    """نمایش یک خبر + افزایش شمارنده بازدید

    - بازدیدکنندهٔ عادی: فقط خبر منتشرشده
      (status=PUBLISHED و رسیدن زمان انتشار)
    - ادمین (staff): همهٔ خبرها را می‌بیند، حتی پیش‌نویس‌ها (پیش‌نمایش)
    """
    articles = (
        Article.objects.select_related("category", "author")
        .prefetch_related("tags")
    )

    if _is_staff(request.user):
        # ادمین: پیش‌نمایش همهٔ وضعیت‌ها (پیش‌نویس / زمان‌بندی‌شده / منتشرشده)
        article = get_object_or_404(articles, slug=slug)
    else:
        # بازدیدکنندهٔ عادی: فقط خبر منتشرشده
        article = get_object_or_404(
            articles,
            slug=slug,
            status=Article.Status.PUBLISHED,
            published_at__lte=timezone.now(),
        )

    # شمارندهٔ بازدید فقط برای بازدیدهای عمومی (غیر ادمین) افزایش می‌یابد
    if not _is_staff(request.user):
        Article.objects.filter(pk=article.pk).update(
            views_count=article.views_count + 1
        )
        article.views_count += 1

    related_articles = (
        Article.objects.filter(
            category=article.category,
            status=Article.Status.PUBLISHED,
            published_at__lte=timezone.now(),
        )
        .exclude(pk=article.pk)
        .select_related("category")[:3]
    )

    context = {
        "article": article,
        "related_articles": related_articles,
    }
    return render(request, "news_modal/article_detail.html", context)


# ---------------------------------------------------------------
# مدیریت خبر (نیازمند ورود + دسترسی مدیریت)
# ---------------------------------------------------------------

@login_required
def article_create(request):
    """صفحه ساخت خبر جدید"""
    if not _is_staff(request.user):
        messages.error(request, "شما مجاز به این عملیات نیستید.")
        return redirect("news_modal:article_list")

    if request.method == "POST":
        form = ArticleForm(request.POST, request.FILES)
        if form.is_valid():
            article = form.save(commit=False)
            article.author = request.user
            article.save()
            form.save_m2m()
            messages.success(request, "خبر با موفقیت ایجاد شد.")
            # چون ادمین در article_detail به پیش‌نویس‌ها هم دسترسی دارد،
            # هدایت به صفحهٔ جزئیات دیگر 404 نمی‌دهد.
            return redirect("news_modal:article_detail", slug=article.slug)
    else:
        form = ArticleForm()

    context = {"form": form, "title": "ایجاد خبر جدید"}
    return render(request, "news_modal/article_form.html", context)


@login_required
def article_update(request, slug):
    """صفحه ویرایش خبر"""
    if not _is_staff(request.user):
        messages.error(request, "شما مجاز به این عملیات نیستید.")
        return redirect("news_modal:article_list")

    article = get_object_or_404(Article, slug=slug)

    if request.method == "POST":
        form = ArticleForm(request.POST, request.FILES, instance=article)
        if form.is_valid():
            form.save()
            messages.success(request, "خبر با موفقیت ویرایش شد.")
            return redirect("news_modal:article_detail", slug=article.slug)
    else:
        form = ArticleForm(instance=article)

    context = {"form": form, "title": "ویرایش خبر", "article": article}
    return render(request, "news_modal/article_form.html", context)


@login_required
def article_delete(request, slug):
    """حذف خبر (با تأیید)"""
    if not _is_staff(request.user):
        messages.error(request, "شما مجاز به این عملیات نیستید.")
        return redirect("news_modal:article_list")

    article = get_object_or_404(Article, slug=slug)

    if request.method == "POST":
        article.delete()
        messages.success(request, "خبر با موفقیت حذف شد.")
        return redirect("news_modal:article_list")

    context = {"article": article}
    return render(request, "news_modal/article_confirm_delete.html", context)


# ---------------------------------------------------------------
# مدیریت دسته‌بندی‌ها
# ---------------------------------------------------------------

@login_required
def category_list(request):
    if not _is_staff(request.user):
        messages.error(request, "شما مجاز به این عملیات نیستید.")
        return redirect("news_modal:article_list")

    categories = Category.objects.all()
    context = {"categories": categories}
    return render(request, "news_modal/category_list.html", context)


@login_required
def category_create(request):
    if not _is_staff(request.user):
        messages.error(request, "شما مجاز به این عملیات نیستید.")
        return redirect("news_modal:article_list")

    if request.method == "POST":
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "دسته‌بندی با موفقیت ایجاد شد.")
            return redirect("news_modal:category_list")
    else:
        form = CategoryForm()

    context = {"form": form, "title": "ایجاد دسته‌بندی"}
    return render(request, "news_modal/category_form.html", context)


@login_required
def category_update(request, pk):
    if not _is_staff(request.user):
        messages.error(request, "شما مجاز به این عملیات نیستید.")
        return redirect("news_modal:article_list")

    category = get_object_or_404(Category, pk=pk)

    if request.method == "POST":
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, "دسته‌بندی با موفقیت ویرایش شد.")
            return redirect("news_modal:category_list")
    else:
        form = CategoryForm(instance=category)

    context = {"form": form, "title": "ویرایش دسته‌بندی", "category": category}
    return render(request, "news_modal/category_form.html", context)


@login_required
def category_delete(request, pk):
    if not _is_staff(request.user):
        messages.error(request, "شما مجاز به این عملیات نیستید.")
        return redirect("news_modal:article_list")

    category = get_object_or_404(Category, pk=pk)

    if request.method == "POST":
        try:
            category.delete()
            messages.success(request, "دسته‌بندی با موفقیت حذف شد.")
        except Exception:
            messages.error(request, "این دسته‌بندی به دلیل داشتن خبر قابل حذف نیست.")
        return redirect("news_modal:category_list")

    context = {"category": category}
    return render(request, "news_modal/category_confirm_delete.html", context)


# ---------------------------------------------------------------
# مدیریت تگ‌ها
# ---------------------------------------------------------------

@login_required
def tag_create(request):
    if not _is_staff(request.user):
        messages.error(request, "شما مجاز به این عملیات نیستید.")
        return redirect("news_modal:article_list")

    if request.method == "POST":
        form = TagForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "تگ با موفقیت ایجاد شد.")
            return redirect("news_modal:article_list")
    else:
        form = TagForm()

    context = {"form": form, "title": "ایجاد تگ"}
    return render(request, "news_modal/tag_form.html", context)


@login_required
def tag_update(request, pk):
    if not _is_staff(request.user):
        messages.error(request, "شما مجاز به این عملیات نیستید.")
        return redirect("news_modal:article_list")

    tag = get_object_or_404(Tag, pk=pk)

    if request.method == "POST":
        form = TagForm(request.POST, instance=tag)
        if form.is_valid():
            form.save()
            messages.success(request, "تگ با موفقیت ویرایش شد.")
            return redirect("news_modal:article_list")
    else:
        form = TagForm(instance=tag)

    context = {"form": form, "title": "ویرایش تگ", "tag": tag}
    return render(request, "news_modal/tag_form.html", context)


@login_required
def tag_delete(request, pk):
    if not _is_staff(request.user):
        messages.error(request, "شما مجاز به این عملیات نیستید.")
        return redirect("news_modal:article_list")

    tag = get_object_or_404(Tag, pk=pk)

    if request.method == "POST":
        tag.delete()
        messages.success(request, "تگ با موفقیت حذف شد.")
        return redirect("news_modal:article_list")

    context = {"tag": tag}
    return render(request, "news_modal/tag_confirm_delete.html", context)
