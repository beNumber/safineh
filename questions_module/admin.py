from django.contrib import admin
from django import forms
from users_module.models import Access
from .models import (
    Chapter, Question, Choice,
    PracticeSession, ExamSession, PracticeAnswer, ExamAnswer, Category
)


def has_access(user, code, subject=None):
    return user.is_authenticated and user.has_project_access(code, subject)


# ─────────────────────────────────────────────────────────────
# ۱. ثبت دسته‌بندی
# ─────────────────────────────────────────────────────────────
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)

    def has_add_permission(self, request):
        return has_access(request.user, Access.Code.CREATE_QUESTION)

    def has_change_permission(self, request, obj=None):
        return has_access(request.user, Access.Code.CREATE_QUESTION)


# ─────────────────────────────────────────────────────────────
# ۲. مدیریت درس‌ها و فصل‌ها
# ─────────────────────────────────────────────────────────────
@admin.register(Chapter)
class ChapterAdmin(admin.ModelAdmin):
    fields = ("subject", "name")
    list_display = ("name", "subject", "questions_count")
    list_filter = ("subject",)
    search_fields = ("name", "subject__title")

    def questions_count(self, obj):
        return obj.questions.count()
    questions_count.short_description = "تعداد سوالات"

    def has_add_permission(self, request):
        return has_access(request.user, Access.Code.CREATE_CHAPTER)

    def has_module_permission(self, request):
        return has_access(request.user, Access.Code.CREATE_CHAPTER)

    def has_view_permission(self, request, obj=None):
        return has_access(
            request.user,
            Access.Code.CREATE_CHAPTER,
            obj.subject if obj else None,
        )

    def has_change_permission(self, request, obj=None):
        return has_access(
            request.user,
            Access.Code.CREATE_CHAPTER,
            obj.subject if obj else None,
        )

    def has_delete_permission(self, request, obj=None):
        return self.has_change_permission(request, obj)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'subject' and not request.user.is_superuser:
            accesses = request.user.accesses.filter(name=Access.Code.CREATE_CHAPTER)
            if not accesses.filter(subject__isnull=True).exists():
                kwargs['queryset'] = db_field.remote_field.model.objects.filter(
                    pk__in=accesses.values_list('subject_id', flat=True)
                )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if request.user.is_superuser:
            return queryset
        accesses = request.user.accesses.filter(name=Access.Code.CREATE_CHAPTER)
        if accesses.filter(subject__isnull=True).exists():
            return queryset
        return queryset.filter(subject_id__in=accesses.values_list('subject_id', flat=True))


# ─────────────────────────────────────────────────────────────
# ۳. گزینه‌های تستی و اعتبارسنجی
# ─────────────────────────────────────────────────────────────
class ChoiceInlineFormSet(forms.models.BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return

        valid_choices = [
            form for form in self.forms
            if form.cleaned_data and not form.cleaned_data.get('DELETE', False)
            and (
                form.cleaned_data.get('text', '').strip()
                or form.cleaned_data.get('image')
                or (form.instance.pk and form.instance.image)
            )
        ]

        if not valid_choices:
            return

        correct_count = sum(
            1 for form in valid_choices if form.cleaned_data.get('is_correct')
        )

        if len(valid_choices) != 4:
            raise forms.ValidationError("هر سؤال باید دقیقاً چهار گزینه داشته باشد.")

        if correct_count == 0:
            raise forms.ValidationError("لطفاً یک گزینه را به عنوان پاسخ صحیح انتخاب کنید.")
        elif correct_count > 1:
            raise forms.ValidationError("تنها یک گزینه می‌تواند پاسخ صحیح باشد.")


class ChoiceInline(admin.TabularInline):
    model = Choice
    formset = ChoiceInlineFormSet
    extra = 4
    min_num = 4
    max_num = 4
    fields = ("text", "image", "is_correct")


# ─────────────────────────────────────────────────────────────
# ۴. مدیریت سوالات
# ─────────────────────────────────────────────────────────────
@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = (
        "short_text", 
        "creator",
        "get_course", 
        "chapter", 
        "difficulty", 
        "approval_status",
        "is_active", 
        "choices_status"
    )
    list_filter = (
        "is_active", 
        "approval_status",
        "difficulty", 
        "chapter__subject",
        "chapter"
    )
    search_fields = ("text", "explanation", "chapter__name", "chapter__subject__title")
    list_editable = ("is_active",)
    inlines = [ChoiceInline]
    save_on_top = True

    fieldsets = (
        ("اطلاعات دسته‌بندی", {
            "fields": (("chapter", "category"), "difficulty", "approval_status", "is_active")
        }),
        ("محتوای سوال", {
            "fields": ("text", "image", "explanation")
        }),
        ("گردش تأیید", {
            "fields": ("creator", "approved_by", "approved_at", "approval_note"),
        }),
    )

    def short_text(self, obj):
        if not obj.text:
            return "سؤال تصویری"
        return obj.text[:60] + "..." if len(obj.text) > 60 else obj.text
    short_text.short_description = "متن سوال"

    def get_readonly_fields(self, request, obj=None):
        return ('creator', 'approved_by', 'approved_at')

    def get_course(self, obj):
        return obj.chapter.subject.title if obj.chapter and obj.chapter.subject else "-"
    get_course.short_description = "درس"
    get_course.admin_order_field = "chapter__subject__title"

    def has_add_permission(self, request):
        return has_access(request.user, Access.Code.CREATE_QUESTION)

    def has_module_permission(self, request):
        return has_access(request.user, Access.Code.CREATE_QUESTION)

    def has_view_permission(self, request, obj=None):
        return has_access(
            request.user,
            Access.Code.CREATE_QUESTION,
            obj.chapter.subject if obj else None,
        )

    def has_change_permission(self, request, obj=None):
        return has_access(
            request.user,
            Access.Code.CREATE_QUESTION,
            obj.chapter.subject if obj else None,
        )

    def has_delete_permission(self, request, obj=None):
        return self.has_change_permission(request, obj)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'chapter':
            chapters = Chapter.objects.filter(subject__is_active=True)
            accesses = request.user.accesses.filter(name=Access.Code.CREATE_QUESTION)
            if not request.user.is_superuser and not accesses.filter(subject__isnull=True).exists():
                chapters = chapters.filter(subject_id__in=accesses.values_list('subject_id', flat=True))
            kwargs['queryset'] = chapters.select_related('subject')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if request.user.is_superuser:
            return queryset
        accesses = request.user.accesses.filter(name=Access.Code.CREATE_QUESTION)
        if accesses.filter(subject__isnull=True).exists():
            return queryset
        return queryset.filter(
            chapter__subject_id__in=accesses.values_list('subject_id', flat=True)
        )

    def choices_status(self, obj):
        count = obj.choices.count()
        correct = obj.choices.filter(is_correct=True).count()
        return f"{count} گزینه ({correct} صحیح)"
    choices_status.short_description = "وضعیت گزینه‌ها"

    def save_model(self, request, obj, form, change):
        if not change and hasattr(obj, 'creator_id') and not obj.creator_id:
            obj.creator = request.user
        super().save_model(request, obj, form, change)


# ─────────────────────────────────────────────────────────────
# ۵. نشست‌های تمرین و آزمون
# ─────────────────────────────────────────────────────────────
@admin.register(PracticeSession)
class PracticeSessionAdmin(admin.ModelAdmin):
    list_display = ("user", "status", "percent", "correct_count", "wrong_count")
    list_filter = ("status",)
    readonly_fields = [f.name for f in PracticeSession._meta.fields]


@admin.register(ExamSession)
class ExamSessionAdmin(admin.ModelAdmin):
    list_display = ("user", "status", "percent", "correct_count", "wrong_count")
    list_filter = ("status", "auto_submitted")
    readonly_fields = [f.name for f in ExamSession._meta.fields]
