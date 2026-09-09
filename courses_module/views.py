from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Avg, Count, Exists, FloatField, OuterRef, Q, Value
from django.db.models.functions import Coalesce
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.text import slugify
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from auth_module.models import Student, UserRole

from .forms import CourseCreateForm
from .models import ApprovalStatus, Course, CourseEnrollment, CourseRating


def course_cards(queryset, user):
    enrollments = CourseEnrollment.objects.filter(course=OuterRef("pk"), student=user)
    return queryset.select_related("author").prefetch_related("subjects").annotate(
        rating_average=Coalesce(Avg("ratings__value"), Value(0.0), output_field=FloatField()),
        rating_count=Count("ratings", distinct=True),
        is_enrolled=Exists(enrollments),
    ).order_by("-created_at")


class RoleRequiredMixin(LoginRequiredMixin):
    allowed_roles = ()
    allow_superuser = False

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if request.user.role not in self.allowed_roles and not (self.allow_superuser and request.user.is_superuser):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class CourseListView(LoginRequiredMixin, ListView):
    model = Course
    template_name = "courses_module/course_list.html"
    context_object_name = "courses"
    paginate_by = 9

    def get_queryset(self):
        user = self.request.user
        now = timezone.now()
        published = Q(approval_status=ApprovalStatus.APPROVED, is_active=True, start_date__lte=now) & (
            Q(end_date__isnull=True) | Q(end_date__gte=now)
        )
        if user.role == UserRole.CONSULTANT:
            queryset = Course.objects.filter(published | Q(author=user))
        elif user.role == UserRole.ADMIN or user.is_superuser:
            queryset = Course.objects.all()
        elif user.role == UserRole.PROVINCE_TRUSTEE:
            queryset = Course.objects.filter(published)
        else:
            queryset = Course.objects.filter(published)
            student = Student.objects.filter(user=user).select_related("field__grade").first()
            if student:
                queryset = queryset.filter(Q(all_fields_allowed=True) | Q(allowed_fields=student.field)).filter(
                    Q(all_grades_allowed=True) | Q(allowed_grades=student.field.grade)
                )
        return course_cards(queryset.distinct(), user)


class MyCoursesView(RoleRequiredMixin, ListView):
    allowed_roles = (UserRole.STUDENT, UserRole.PROVINCE_TRUSTEE)
    model = Course
    template_name = "courses_module/my_courses.html"
    context_object_name = "courses"

    def get_queryset(self):
        if self.request.user.role == UserRole.PROVINCE_TRUSTEE:
            return Course.objects.filter(approval_status=ApprovalStatus.PENDING).select_related("author").prefetch_related(
                "subjects", "allowed_grades", "allowed_fields"
            )
        queryset = Course.objects.published().filter(enrollments__student=self.request.user).distinct()
        return course_cards(queryset, self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_trustee_queue"] = self.request.user.role == UserRole.PROVINCE_TRUSTEE
        return context


class CourseDetailView(LoginRequiredMixin, DetailView):
    model = Course
    template_name = "courses_module/course_detail.html"
    context_object_name = "course"
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.role in (UserRole.PROVINCE_TRUSTEE, UserRole.ADMIN):
            return Course.objects.all()
        if user.role == UserRole.CONSULTANT:
            return Course.objects.filter(Q(author=user) | Q(pk__in=Course.objects.published()))
        return Course.objects.published()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context["sections"] = self.object.sections.prefetch_related("episodes").all()
        context["rating_average"] = self.object.average_rating
        context["rating_count"] = self.object.ratings.count()
        context["is_enrolled"] = self.object.enrollments.filter(student=user).exists()
        rating = self.object.ratings.filter(student=user).first()
        context["user_rating"] = rating.value if rating else 0
        return context


class CourseCreateView(RoleRequiredMixin, CreateView):
    allowed_roles = (UserRole.CONSULTANT,)
    model = Course
    form_class = CourseCreateForm
    template_name = "courses_module/course_form.html"
    success_url = reverse_lazy("courses_module:course_list")

    def form_valid(self, form):
        form.instance.author = self.request.user
        form.instance.approval_status = ApprovalStatus.PENDING
        form.instance.is_active = True
        base_slug = slugify(form.cleaned_data["title"], allow_unicode=True) or "course"
        slug = base_slug
        counter = 2
        while Course.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        form.instance.slug = slug
        response = super().form_valid(form)
        subjects = form.cleaned_data["subjects"]
        self.object.topic = "، ".join(subjects.values_list("title", flat=True))[:255]
        self.object.save(update_fields=["topic"])
        messages.success(self.request, "درخواست ساخت دوره ثبت شد و برای تأیید به معتمد استان ارسال گردید.")
        return response


class CourseUpdateView(RoleRequiredMixin, UpdateView):
    """Edit a course according to the role-specific ownership rules."""
    allowed_roles = (UserRole.CONSULTANT, UserRole.PROVINCE_TRUSTEE, UserRole.ADMIN)
    allow_superuser = True
    model = Course
    form_class = CourseCreateForm
    template_name = "courses_module/course_form.html"

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.role == UserRole.ADMIN:
            return Course.objects.all()
        if user.role == UserRole.CONSULTANT:
            return Course.objects.filter(author=user)
        if user.role == UserRole.PROVINCE_TRUSTEE:
            return Course.objects.all()
        return Course.objects.none()

    def get_success_url(self):
        return reverse_lazy("courses_module:course_detail", kwargs={"slug": self.object.slug})

    def form_valid(self, form):
        # Any edit after review must return to the trustee queue.
        if self.request.user.role == UserRole.CONSULTANT and self.object.approval_status != ApprovalStatus.PENDING:
            form.instance.approval_status = ApprovalStatus.PENDING
            form.instance.reviewed_by = None
            form.instance.reviewed_at = None
        response = super().form_valid(form)
        subjects = form.cleaned_data.get("subjects")
        if subjects is not None:
            self.object.topic = "، ".join(subjects.values_list("title", flat=True))[:255]
            self.object.save(update_fields=["topic"])
        messages.success(self.request, "تغییرات دوره با موفقیت ذخیره شد.")
        return response


class EnrollCourseView(RoleRequiredMixin, View):
    allowed_roles = (UserRole.STUDENT,)

    def post(self, request, slug):
        with transaction.atomic():
            course = get_object_or_404(Course.objects.select_for_update().published(), slug=slug)
            if CourseEnrollment.objects.filter(course=course, student=request.user).exists():
                messages.info(request, "این دوره از قبل در دوره‌های من قرار دارد.")
                return redirect("courses_module:course_detail", slug=slug)
            if course.capacity is not None and course.enrollments.count() >= course.capacity:
                messages.error(request, "ظرفیت این دوره تکمیل شده است.")
                return redirect("courses_module:course_detail", slug=slug)
            CourseEnrollment.objects.create(course=course, student=request.user)
        messages.success(request, "دوره با موفقیت به «دوره‌های من» اضافه شد.")
        return redirect("courses_module:my_courses")


class RateCourseView(RoleRequiredMixin, View):
    allowed_roles = (UserRole.STUDENT,)

    def post(self, request, slug):
        course = get_object_or_404(Course.objects.published(), slug=slug)
        if not CourseEnrollment.objects.filter(course=course, student=request.user).exists():
            messages.error(request, "برای امتیاز دادن ابتدا در دوره شرکت کنید.")
            return redirect("courses_module:course_detail", slug=slug)
        try:
            value = int(request.POST.get("rating", ""))
        except (TypeError, ValueError):
            return HttpResponseBadRequest("امتیاز نامعتبر است.")
        if value not in range(1, 6):
            return HttpResponseBadRequest("امتیاز باید بین ۱ تا ۵ باشد.")
        CourseRating.objects.update_or_create(course=course, student=request.user, defaults={"value": value})
        messages.success(request, "امتیاز شما ثبت شد.")
        return redirect("courses_module:course_detail", slug=slug)


class CourseReviewListView(RoleRequiredMixin, ListView):
    allowed_roles = (UserRole.PROVINCE_TRUSTEE,)
    model = Course
    template_name = "courses_module/review_list.html"
    context_object_name = "courses"

    def get_queryset(self):
        return Course.objects.filter(approval_status=ApprovalStatus.PENDING).select_related("author").prefetch_related(
            "subjects", "allowed_grades", "allowed_fields"
        )


class CourseReviewView(RoleRequiredMixin, View):
    allowed_roles = (UserRole.PROVINCE_TRUSTEE,)

    def post(self, request, pk):
        course = get_object_or_404(Course, pk=pk, approval_status=ApprovalStatus.PENDING)
        action = request.POST.get("action")
        if action == "approve":
            course.approval_status = ApprovalStatus.APPROVED
            course.rejection_reason = ""
            message = "دوره تأیید و منتشر شد."
        elif action == "reject":
            course.approval_status = ApprovalStatus.REJECTED
            course.rejection_reason = request.POST.get("reason", "").strip()
            message = "دوره رد شد و نتیجه برای مشاور ثبت گردید."
        else:
            return HttpResponseBadRequest("عملیات نامعتبر است.")
        course.reviewed_by = request.user
        course.reviewed_at = timezone.now()
        course.save(update_fields=["approval_status", "rejection_reason", "reviewed_by", "reviewed_at"])
        messages.success(request, message)
        return redirect("courses_module:review_list")


class AdminCourseCloseView(RoleRequiredMixin, View):
    allowed_roles = (UserRole.ADMIN,)
    allow_superuser = True

    def post(self, request, pk):
        course = get_object_or_404(Course, pk=pk)
        course.is_active = False
        course.save(update_fields=["is_active", "updated_at"])
        messages.success(request, "دوره بسته شد و دیگر برای دانش‌آموزان نمایش داده نمی‌شود.")
        return redirect("courses_module:course_detail", slug=course.slug)


class AdminCourseDeleteView(RoleRequiredMixin, View):
    allowed_roles = (UserRole.ADMIN,)
    allow_superuser = True

    def post(self, request, pk):
        course = get_object_or_404(Course, pk=pk)
        title = course.title
        course.delete()
        messages.success(request, f"دوره «{title}» حذف شد.")
        return redirect("courses_module:course_list")
