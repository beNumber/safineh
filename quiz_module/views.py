from statistics import mean, pstdev

from PIL import Image, UnidentifiedImageError
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Avg, Count, Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from auth_module.models import UserRole
from questions_module.models import Question

from .forms import BankImportForm, ManualGradeForm, QuizChoiceFormSet, QuizForm, QuizQuestionForm
from .models import Quiz, QuizAnswer, QuizAttempt, QuizChoice, QuizQuestion
from .permissions import can_create_quiz, can_edit_quiz_questions, can_manage_quiz, can_review_quiz, can_view_results, is_quiz_admin, trustee_province_ids
from .services import create_attempt, enqueue_quiz_questions, finalize_attempt, log_tab_event, recalculate_attempt


def _student_can_take(user, quiz):
    if user.role != UserRole.STUDENT or quiz.status != Quiz.Status.APPROVED:
        return False
    if quiz.all_students:
        return True
    assigned = quiz.assigned_students.exists()
    if assigned:
        return quiz.assigned_students.filter(pk=user.pk).exists()
    profiles = user.student_profiles.select_related("field__grade__school__province")
    if quiz.field_id:
        profiles = profiles.filter(field_id=quiz.field_id)
    if quiz.grade_id:
        profiles = profiles.filter(field__grade_id=quiz.grade_id)
    if quiz.school_id:
        profiles = profiles.filter(field__grade__school_id=quiz.school_id)
    if quiz.province_id:
        profiles = profiles.filter(field__grade__school__province_id=quiz.province_id)
    return profiles.exists()


def _quiz_queryset_for(user):
    qs = Quiz.objects.select_related("creator", "province", "school", "grade", "field").annotate(attempt_count=Count("attempts", distinct=True))
    if is_quiz_admin(user):
        return qs
    if user.role == UserRole.CONSULTANT:
        return qs.filter(creator=user)
    if user.role == UserRole.PROVINCE_TRUSTEE:
        return qs.filter(province_id__in=trustee_province_ids(user))
    if user.role == UserRole.STUDENT:
        profile_fields = user.student_profiles.values_list("field_id", flat=True)
        profile_grades = user.student_profiles.values_list("field__grade_id", flat=True)
        profile_schools = user.student_profiles.values_list("field__grade__school_id", flat=True)
        profile_provinces = user.student_profiles.values_list("field__grade__school__province_id", flat=True)
        return qs.filter(status=Quiz.Status.APPROVED).filter(
            Q(all_students=True) | Q(assigned_students=user) |
            (Q(assigned_students__isnull=True) &
             (Q(field__isnull=True) | Q(field_id__in=profile_fields)) &
             (Q(grade__isnull=True) | Q(grade_id__in=profile_grades)) &
             (Q(school__isnull=True) | Q(school_id__in=profile_schools)) &
             (Q(province__isnull=True) | Q(province_id__in=profile_provinces)))
        ).distinct()
    return qs.none()


def _mark_consultant_quiz_changed(user, quiz):
    if user.role == UserRole.CONSULTANT and quiz.status != Quiz.Status.DRAFT:
        quiz.status = Quiz.Status.DRAFT
        quiz.approved_by = None
        quiz.approved_at = None
        quiz.approval_note = ""
        quiz.save(update_fields=["status", "approved_by", "approved_at", "approval_note"])


@login_required
def quiz_list(request):
    quizzes = _quiz_queryset_for(request.user)
    status = request.GET.get("status")
    if status in Quiz.Status.values:
        quizzes = quizzes.filter(status=status)
    for quiz in quizzes.filter(closes_at__lte=timezone.now()):
        enqueue_quiz_questions(quiz)
    return render(request, "quiz_module/quiz_list.html", {"quizzes": quizzes, "can_create": can_create_quiz(request.user), "now": timezone.now()})


@login_required
def quiz_create(request):
    if not can_create_quiz(request.user):
        messages.error(request, "برای ساخت آزمون باید دسترسی آزمون از طرف مدیر برای شما فعال شود.")
        return redirect("quiz_module:quiz_list")
    form = QuizForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        quiz = form.save(commit=False)
        quiz.creator = request.user
        quiz.status = Quiz.Status.DRAFT
        quiz.save()
        form.instance = quiz
        form.save_m2m()
        messages.success(request, "اطلاعات آزمون ذخیره شد؛ اکنون سؤال‌ها را اضافه کنید.")
        return redirect("quiz_module:quiz_builder", pk=quiz.pk)
    return render(request, "quiz_module/quiz_form.html", {"form": form, "title": "ساخت آزمون جدید"})


@login_required
def quiz_edit(request, pk):
    quiz = get_object_or_404(Quiz, pk=pk)
    if not can_manage_quiz(request.user, quiz):
        raise Http404
    form = QuizForm(request.POST or None, instance=quiz)
    if request.method == "POST" and form.is_valid():
        form.save()
        _mark_consultant_quiz_changed(request.user, quiz)
        messages.success(request, "تنظیمات آزمون به‌روزرسانی شد.")
        return redirect("quiz_module:quiz_builder", pk=quiz.pk)
    return render(request, "quiz_module/quiz_form.html", {"form": form, "quiz": quiz, "title": "ویرایش آزمون"})


@login_required
def quiz_builder(request, pk):
    quiz = get_object_or_404(Quiz.objects.prefetch_related("questions__choices"), pk=pk)
    if not can_edit_quiz_questions(request.user, quiz):
        raise Http404
    quiz.sync_question_count()
    return render(request, "quiz_module/quiz_builder.html", {"quiz": quiz})


@login_required
def question_create(request, pk):
    quiz = get_object_or_404(Quiz, pk=pk)
    if not can_edit_quiz_questions(request.user, quiz):
        raise Http404
    question = QuizQuestion(quiz=quiz, order=quiz.questions.count())
    form = QuizQuestionForm(request.POST or None, request.FILES or None, instance=question)
    formset = QuizChoiceFormSet(request.POST or None, request.FILES or None, instance=question)
    if request.method == "POST" and form.is_valid():
        question = form.save(commit=False)
        question.quiz = quiz
        formset.instance = question
        if formset.is_valid():
            with transaction.atomic():
                question.save()
                if question.question_type == QuizQuestion.Type.MCQ:
                    formset.save()
                quiz.sync_question_count()
                _mark_consultant_quiz_changed(request.user, quiz)
            messages.success(request, "سؤال جدید به آزمون اضافه شد.")
            return redirect("quiz_module:quiz_builder", pk=quiz.pk)
    return render(request, "quiz_module/question_form.html", {"quiz": quiz, "form": form, "formset": formset, "title": "سؤال جدید"})


@login_required
def question_edit(request, pk, question_id):
    quiz = get_object_or_404(Quiz, pk=pk)
    if not can_edit_quiz_questions(request.user, quiz):
        raise Http404
    question = get_object_or_404(QuizQuestion, pk=question_id, quiz=quiz)
    form = QuizQuestionForm(request.POST or None, request.FILES or None, instance=question)
    formset = QuizChoiceFormSet(request.POST or None, request.FILES or None, instance=question)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            form.save()
            if question.question_type == QuizQuestion.Type.MCQ:
                formset.save()
            else:
                question.choices.all().delete()
            _mark_consultant_quiz_changed(request.user, quiz)
        messages.success(request, "سؤال ویرایش شد.")
        return redirect("quiz_module:quiz_builder", pk=quiz.pk)
    return render(request, "quiz_module/question_form.html", {"quiz": quiz, "form": form, "formset": formset, "title": "ویرایش سؤال"})


@login_required
@require_POST
def question_delete(request, pk, question_id):
    quiz = get_object_or_404(Quiz, pk=pk)
    if not can_edit_quiz_questions(request.user, quiz):
        raise Http404
    get_object_or_404(QuizQuestion, pk=question_id, quiz=quiz).delete()
    quiz.sync_question_count()
    _mark_consultant_quiz_changed(request.user, quiz)
    messages.success(request, "سؤال حذف شد.")
    return redirect("quiz_module:quiz_builder", pk=quiz.pk)


@login_required
def bank_import(request, pk):
    quiz = get_object_or_404(Quiz, pk=pk)
    if not can_edit_quiz_questions(request.user, quiz):
        raise Http404
    form = BankImportForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            order = quiz.questions.count()
            for source in form.cleaned_data["questions"]:
                item = QuizQuestion.objects.create(
                    quiz=quiz, source_question=source, bank_topic=source.topic, question_type=source.question_type,
                    text=source.text, image=source.image, explanation=source.explanation, points=1, order=order,
                    submit_to_bank=False,
                )
                for index, choice in enumerate(source.choices.all()):
                    QuizChoice.objects.create(question=item, text=choice.text, image=choice.image, is_correct=choice.is_correct, order=index)
                order += 1
            quiz.sync_question_count()
            _mark_consultant_quiz_changed(request.user, quiz)
        messages.success(request, "سؤال‌های انتخاب‌شده از بانک سؤال افزوده شدند.")
        return redirect("quiz_module:quiz_builder", pk=quiz.pk)
    return render(request, "quiz_module/bank_import.html", {"quiz": quiz, "form": form})


@login_required
@require_POST
def submit_for_review(request, pk):
    quiz = get_object_or_404(Quiz, pk=pk)
    if not can_manage_quiz(request.user, quiz):
        raise Http404
    if not quiz.questions.exists():
        messages.error(request, "آزمون بدون سؤال قابل ارسال نیست.")
    elif request.user.role == UserRole.CONSULTANT and not quiz.province_id:
        messages.error(request, "برای ارسال به معتمد، استان مخاطب را مشخص کنید.")
    else:
        quiz.status = Quiz.Status.APPROVED if is_quiz_admin(request.user) else Quiz.Status.PENDING
        quiz.approved_by = request.user if is_quiz_admin(request.user) else None
        quiz.approved_at = timezone.now() if is_quiz_admin(request.user) else None
        quiz.save(update_fields=["status", "approved_by", "approved_at"])
        messages.success(request, "آزمون فعال شد." if is_quiz_admin(request.user) else "آزمون برای تأیید معتمد استان ارسال شد.")
    return redirect("quiz_module:quiz_list")


@login_required
def approval_queue(request):
    if not (is_quiz_admin(request.user) or request.user.role == UserRole.PROVINCE_TRUSTEE):
        raise Http404
    qs = Quiz.objects.filter(status=Quiz.Status.PENDING).select_related("creator", "province")
    if not is_quiz_admin(request.user):
        qs = qs.filter(province_id__in=trustee_province_ids(request.user))
    return render(request, "quiz_module/approval_queue.html", {"quizzes": qs})


@login_required
@require_POST
def review_quiz(request, pk):
    quiz = get_object_or_404(Quiz, pk=pk, status=Quiz.Status.PENDING)
    if not can_review_quiz(request.user, quiz):
        raise Http404
    action = request.POST.get("action")
    if action not in {"approve", "reject"}:
        return redirect("quiz_module:approval_queue")
    quiz.status = Quiz.Status.APPROVED if action == "approve" else Quiz.Status.REJECTED
    quiz.approval_note = request.POST.get("note", "").strip()
    quiz.approved_by = request.user
    quiz.approved_at = timezone.now()
    quiz.save(update_fields=["status", "approval_note", "approved_by", "approved_at"])
    messages.success(request, "نتیجه بررسی ثبت شد.")
    return redirect("quiz_module:approval_queue")


@login_required
def start_quiz(request, pk):
    quiz = get_object_or_404(Quiz, pk=pk)
    if not _student_can_take(request.user, quiz):
        raise Http404
    now = timezone.now()
    if now < quiz.opens_at:
        messages.warning(request, "زمان شروع آزمون هنوز نرسیده است.")
        return redirect("quiz_module:quiz_list")
    if now > quiz.closes_at:
        messages.error(request, "بازه دسترسی این آزمون پایان یافته است.")
        return redirect("quiz_module:quiz_list")
    active = quiz.attempts.filter(student=request.user, status=QuizAttempt.Status.IN_PROGRESS).first()
    if active:
        if active.expires_at <= now:
            finalize_attempt(active, auto=True)
        else:
            return redirect("quiz_module:attempt", attempt_id=active.pk)
    if quiz.attempts.filter(student=request.user).count() >= quiz.max_attempts:
        messages.error(request, "تعداد دفعات مجاز شرکت در آزمون تکمیل شده است.")
        return redirect("quiz_module:quiz_list")
    attempt = create_attempt(quiz, request.user)
    return redirect("quiz_module:attempt", attempt_id=attempt.pk)


def _attempt_for_student(request, attempt_id):
    return get_object_or_404(QuizAttempt.objects.select_related("quiz", "student"), pk=attempt_id, student=request.user)


@login_required
@never_cache
def attempt_view(request, attempt_id):
    attempt = _attempt_for_student(request, attempt_id)
    if attempt.status != QuizAttempt.Status.IN_PROGRESS:
        return redirect("quiz_module:attempt_result", attempt_id=attempt.pk)
    if timezone.now() >= attempt.expires_at:
        finalize_attempt(attempt, auto=True)
        return redirect("quiz_module:attempt_result", attempt_id=attempt.pk)
    question_map = {q.id: q for q in attempt.quiz.questions.prefetch_related("choices")}
    answers = {a.question_id: a for a in attempt.answers.all()}
    rows = []
    for number, question_id in enumerate(attempt.question_order, 1):
        question = question_map.get(question_id)
        if not question:
            continue
        choices = {choice.id: choice for choice in question.choices.all()}
        ordered_choices = [choices[cid] for cid in attempt.choice_order.get(str(question.id), []) if cid in choices]
        rows.append({"number": number, "question": question, "choices": ordered_choices, "answer": answers.get(question.id)})
    return render(request, "quiz_module/attempt.html", {"attempt": attempt, "rows": rows, "remaining_seconds": max(0, int((attempt.expires_at - timezone.now()).total_seconds()))})


@login_required
@require_POST
def save_answer(request, attempt_id, question_id):
    attempt = _attempt_for_student(request, attempt_id)
    if attempt.status != QuizAttempt.Status.IN_PROGRESS or timezone.now() >= attempt.expires_at:
        if attempt.status == QuizAttempt.Status.IN_PROGRESS:
            finalize_attempt(attempt, auto=True)
        return JsonResponse({"ok": False, "expired": True}, status=409)
    question = get_object_or_404(QuizQuestion, pk=question_id, quiz=attempt.quiz)
    answer, _ = QuizAnswer.objects.get_or_create(attempt=attempt, question=question)
    if "bookmarked" in request.POST:
        answer.bookmarked = request.POST.get("bookmarked") == "true"
    if question.question_type == QuizQuestion.Type.MCQ and "choice" in request.POST:
        choice_id = request.POST.get("choice")
        answer.choice = get_object_or_404(QuizChoice, pk=choice_id, question=question) if choice_id else None
    if question.question_type == QuizQuestion.Type.DESCRIPTIVE:
        answer.text_answer = request.POST.get("text_answer", answer.text_answer)
        if request.FILES.get("answer_image"):
            upload = request.FILES["answer_image"]
            if upload.size > 5 * 1024 * 1024:
                return JsonResponse({"ok": False, "error": "حجم تصویر نباید بیشتر از ۵ مگابایت باشد."}, status=400)
            try:
                Image.open(upload).verify()
                upload.seek(0)
            except (UnidentifiedImageError, OSError):
                return JsonResponse({"ok": False, "error": "فایل انتخاب‌شده تصویر معتبر نیست."}, status=400)
            answer.answer_image = upload
    answer.save()
    answered = attempt.answers.filter(Q(choice__isnull=False) | ~Q(text_answer="") | ~Q(answer_image="")).distinct().count()
    return JsonResponse({"ok": True, "saved_at": timezone.localtime(answer.saved_at).strftime("%H:%M:%S"), "answered": answered, "bookmarked": answer.bookmarked})


@login_required
@require_POST
def track_event(request, attempt_id):
    attempt = _attempt_for_student(request, attempt_id)
    log_tab_event(attempt, request.POST.get("event"))
    return JsonResponse({"ok": True})


@login_required
@require_POST
def submit_attempt(request, attempt_id):
    attempt = _attempt_for_student(request, attempt_id)
    finalize_attempt(attempt, auto=request.POST.get("auto") == "1")
    return redirect("quiz_module:attempt_result", attempt_id=attempt.pk)


@login_required
def attempt_result(request, attempt_id):
    attempt = get_object_or_404(QuizAttempt.objects.select_related("quiz", "student"), pk=attempt_id)
    if attempt.student_id != request.user.id and not can_view_results(request.user, attempt.quiz):
        raise Http404
    if attempt.student_id == request.user.id and not attempt.quiz.publish_results:
        messages.info(request, "نتیجه این آزمون هنوز توسط برگزارکننده منتشر نشده است.")
        return redirect("quiz_module:quiz_list")
    attempts = QuizAttempt.objects.filter(quiz=attempt.quiz, status=QuizAttempt.Status.GRADED).order_by("-score", "finished_at")
    rank = list(attempts.values_list("id", flat=True)).index(attempt.id) + 1 if attempts.filter(pk=attempt.pk).exists() else None
    scores = [float(value) for value in attempts.values_list("score", flat=True)]
    if scores:
        average, deviation = mean(scores), pstdev(scores)
        t_score = round(max(0, min(10000, 5000 + (2000 * (float(attempt.score) - average) / deviation)))) if deviation else 5000
    else:
        t_score = None
    release_answers = bool(attempt.quiz.answer_release_at and timezone.now() >= attempt.quiz.answer_release_at)
    answers = attempt.answers.select_related("question", "choice").prefetch_related("question__choices")
    return render(request, "quiz_module/attempt_result.html", {"attempt": attempt, "answers": answers, "rank": rank, "participants": attempts.count(), "t_score": t_score, "release_answers": release_answers})


@login_required
def quiz_results(request, pk):
    quiz = get_object_or_404(Quiz, pk=pk)
    if not can_view_results(request.user, quiz):
        raise Http404
    attempts = quiz.attempts.select_related("student").exclude(status=QuizAttempt.Status.IN_PROGRESS).order_by("-score")
    stats = attempts.aggregate(average=Avg("score"), participants=Count("id"))
    pending_count = attempts.filter(status=QuizAttempt.Status.SUBMITTED).count()
    return render(request, "quiz_module/quiz_results.html", {"quiz": quiz, "attempts": attempts, "stats": stats, "pending_count": pending_count})


@login_required
def grade_attempt(request, attempt_id):
    attempt = get_object_or_404(QuizAttempt.objects.select_related("quiz", "student"), pk=attempt_id)
    if not can_view_results(request.user, attempt.quiz):
        raise Http404
    answers = attempt.answers.filter(question__question_type=QuizQuestion.Type.DESCRIPTIVE).select_related("question")
    if request.method == "POST":
        answer = get_object_or_404(answers, pk=request.POST.get("answer_id"))
        form = ManualGradeForm(request.POST)
        if form.is_valid() and form.cleaned_data["points"] <= answer.question.points:
            answer.points_earned = form.cleaned_data["points"]
            answer.grader_note = form.cleaned_data["note"]
            answer.graded_by = request.user
            answer.save(update_fields=["points_earned", "grader_note", "graded_by"])
            recalculate_attempt(attempt)
            messages.success(request, "نمره پاسخ تشریحی ذخیره شد.")
            return redirect("quiz_module:grade_attempt", attempt_id=attempt.pk)
        messages.error(request, "نمره واردشده معتبر نیست یا از بارم سؤال بیشتر است.")
    return render(request, "quiz_module/grade_attempt.html", {"attempt": attempt, "answers": answers})


@login_required
def filter_students(request):
    if not can_create_quiz(request.user):
        return JsonResponse({"results": []}, status=403)
    from django.contrib.auth import get_user_model
    qs = get_user_model().objects.filter(role=UserRole.STUDENT, is_active=True)
    if request.GET.get("school"):
        qs = qs.filter(student_profiles__field__grade__school_id=request.GET["school"])
    if request.GET.get("grade"):
        qs = qs.filter(student_profiles__field__grade_id=request.GET["grade"])
    if request.GET.get("field"):
        qs = qs.filter(student_profiles__field_id=request.GET["field"])
    return JsonResponse({"results": [{"id": user.id, "text": user.get_full_name() or user.username} for user in qs.distinct()[:300]]})
