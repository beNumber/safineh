from django.contrib import admin
from .models import Quiz, QuizQuestion, QuizChoice, QuizAttempt, QuizAnswer
from .forms import QuizForm


class QuizChoiceInline(admin.TabularInline):
    model = QuizChoice
    extra = 4


class QuizQuestionInline(admin.StackedInline):
    model = QuizQuestion
    extra = 0
    show_change_link = True


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    form = QuizForm
    list_display = ('title', 'creator', 'status', 'opens_at', 'closes_at', 'duration_minutes', 'max_attempts', 'created_at')
    list_filter = ('status', 'province', 'school', 'grade', 'field')
    search_fields = ('title', 'creator__username', 'creator__first_name', 'creator__last_name')
    autocomplete_fields = ('creator', 'approved_by')
    date_hierarchy = 'created_at'
    inlines = [QuizQuestionInline]
    fieldsets = (
        ('اطلاعات آزمون', {'fields': ('title', 'description', 'creator', 'status', 'approval_note', 'approved_by')}),
        ('زمان و محدودیت', {'fields': ('duration_minutes', 'max_attempts', 'opens_at', 'closes_at')}),
        ('جامعه هدف', {'fields': ('province', 'school', 'grade', 'field')}),
    )
    readonly_fields = ('created_at', 'updated_at')


@admin.register(QuizQuestion)
class QuizQuestionAdmin(admin.ModelAdmin):
    list_display = ('quiz', 'order', 'points', 'short_text')
    list_filter = ('quiz',)
    inlines = [QuizChoiceInline]

    @admin.display(description='سؤال')
    def short_text(self, obj):
        from django.utils.html import strip_tags
        return strip_tags(obj.text)[:80]


@admin.register(QuizChoice)
class QuizChoiceAdmin(admin.ModelAdmin):
    list_display = ('question', 'order', 'is_correct')
    list_filter = ('is_correct',)


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ('quiz', 'student', 'score', 'total_score', 'correct_count', 'finished_at')
    list_filter = ('quiz', 'finished_at')
    search_fields = ('quiz__title', 'student__username', 'student__first_name', 'student__last_name')
    readonly_fields = ('started_at', 'finished_at', 'score', 'total_score', 'correct_count', 'answered_count')


@admin.register(QuizAnswer)
class QuizAnswerAdmin(admin.ModelAdmin):
    list_display = ('attempt', 'question', 'choice', 'points_earned')
