from django.contrib import admin

from .models import Quiz, QuizAnswer, QuizAttempt, QuizChoice, QuizEvent, QuizQuestion


class QuizChoiceInline(admin.TabularInline):
    model = QuizChoice
    extra = 0


@admin.register(QuizQuestion)
class QuizQuestionAdmin(admin.ModelAdmin):
    list_display = ("quiz", "order", "question_type", "points", "source_question")
    list_filter = ("question_type", "submit_to_bank")
    inlines = (QuizChoiceInline,)


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ("title", "creator", "status", "opens_at", "closes_at", "question_count")
    list_filter = ("status", "province", "negative_marking")
    search_fields = ("title", "creator__username")


admin.site.register(QuizAttempt)
admin.site.register(QuizAnswer)
admin.site.register(QuizEvent)
