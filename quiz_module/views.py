from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Avg
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from auth_module.models import UserRole, Student
from .models import Quiz, QuizQuestion, QuizAttempt, QuizAnswer
from .forms import QuizForm, QuizQuestionForm, ChoiceFormSet


def _can_manage(user):
    return user.is_superuser or user.role in {UserRole.ADMIN, UserRole.PROVINCE_TRUSTEE, UserRole.CONSULTANT}


def _visible_to_student(quiz, user):
    try:
        student = Student.objects.select_related('field__grade__school').get(user=user)
    except Student.DoesNotExist:
        return False
    return all((not value or value == actual) for value, actual in (
        (quiz.province_id, student.field.grade.school.province_id),
        (quiz.school_id, student.field.grade.school_id),
        (quiz.grade_id, student.field.grade_id),
        (quiz.field_id, student.field_id),
    ))


@login_required
def quiz_dashboard(request):
    if request.user.role == UserRole.STUDENT:
        quizzes = [q for q in Quiz.objects.filter(status=Quiz.Status.APPROVED).prefetch_related('questions') if _visible_to_student(q, request.user)]
        attempts = QuizAttempt.objects.filter(student=request.user).select_related('quiz')
        return render(request, 'quiz_module/student_dashboard.html', {'quizzes': quizzes, 'attempts': attempts})
    quizzes = Quiz.objects.filter(creator=request.user) if request.user.role == UserRole.CONSULTANT else Quiz.objects.all()
    return render(request, 'quiz_module/dashboard.html', {'quizzes': quizzes, 'can_create': _can_manage(request.user), 'pending': Quiz.objects.filter(status=Quiz.Status.PENDING).count()})


@login_required
def quiz_create(request):
    if not _can_manage(request.user): return HttpResponseForbidden()
    form = QuizForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        quiz = form.save(commit=False); quiz.creator = request.user
        quiz.status = Quiz.Status.PENDING if request.user.role == UserRole.CONSULTANT else Quiz.Status.APPROVED
        quiz.save(); messages.success(request, 'آزمون ایجاد شد؛ در صورت نیاز برای تأیید ارسال شد.'); return redirect('quiz_module:question_add', quiz.pk)
    return render(request, 'quiz_module/quiz_form.html', {'form': form, 'title': 'ایجاد آزمون'})


@login_required
def quiz_edit(request, pk):
    quiz = get_object_or_404(Quiz, pk=pk)
    if not (_can_manage(request.user) and (request.user.role != UserRole.CONSULTANT or quiz.creator_id == request.user.id and quiz.status == Quiz.Status.PENDING)): return HttpResponseForbidden()
    form = QuizForm(request.POST or None, instance=quiz)
    if request.method == 'POST' and form.is_valid():
        quiz = form.save(commit=False)
        if request.user.role == UserRole.CONSULTANT: quiz.status = Quiz.Status.PENDING; quiz.approved_by = None
        quiz.save(); return redirect('quiz_module:dashboard')
    return render(request, 'quiz_module/quiz_form.html', {'form': form, 'title': 'ویرایش آزمون'})


@login_required
def quiz_delete(request, pk):
    quiz = get_object_or_404(Quiz, pk=pk)
    if request.user.role == UserRole.CONSULTANT and (quiz.creator_id != request.user.id or quiz.status != Quiz.Status.PENDING): return HttpResponseForbidden()
    if request.method == 'POST': quiz.delete(); messages.success(request, 'آزمون حذف شد.')
    return redirect('quiz_module:dashboard')


@login_required
def question_add(request, pk):
    quiz = get_object_or_404(Quiz, pk=pk)
    if quiz.creator_id != request.user.id and not request.user.is_superuser: return HttpResponseForbidden()
    current_count = quiz.questions.count()
    if current_count >= quiz.question_count:
        messages.info(request, 'تعداد تعیین‌شده سؤال‌ها تکمیل شده است.'); return redirect('quiz_module:dashboard')
    form = QuizQuestionForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        q = form.save(commit=False); q.quiz = quiz; q.save(); fs = ChoiceFormSet(request.POST, request.FILES, instance=q)
        if fs.is_valid():
            fs.save(); return redirect('quiz_module:question_add', pk)
        q.delete()
    else: fs = ChoiceFormSet(instance=QuizQuestion())
    return render(request, 'quiz_module/question_form.html', {'form': form, 'formset': fs, 'quiz': quiz, 'current_count': current_count, 'remaining_count': quiz.question_count - current_count})


@login_required
def approval_queue(request):
    if request.user.role not in {UserRole.ADMIN, UserRole.PROVINCE_TRUSTEE} and not request.user.is_superuser: return HttpResponseForbidden()
    return render(request, 'quiz_module/approval.html', {'quizzes': Quiz.objects.filter(status=Quiz.Status.PENDING).select_related('creator')})


@login_required
def review_quiz(request, pk):
    if request.user.role not in {UserRole.ADMIN, UserRole.PROVINCE_TRUSTEE} and not request.user.is_superuser: return HttpResponseForbidden()
    quiz = get_object_or_404(Quiz, pk=pk)
    if request.method == 'POST':
        quiz.status = request.POST.get('decision'); quiz.approval_note = request.POST.get('note', ''); quiz.approved_by = request.user; quiz.save(update_fields=['status','approval_note','approved_by','updated_at'])
    return redirect('quiz_module:approval')


@login_required
def quiz_start(request, pk):
    quiz = get_object_or_404(Quiz, pk=pk, status=Quiz.Status.APPROVED)
    if request.user.role != UserRole.STUDENT or not quiz.is_open or not _visible_to_student(quiz, request.user): return HttpResponseForbidden()
    if QuizAttempt.objects.filter(quiz=quiz, student=request.user).count() >= quiz.max_attempts: return HttpResponseForbidden('دفعات مجاز شرکت در آزمون به پایان رسیده است.')
    attempt = QuizAttempt.objects.create(quiz=quiz, student=request.user, total_score=sum((q.points for q in quiz.questions.all()), Decimal('0')))
    return redirect('quiz_module:attempt', attempt.pk)


@login_required
def quiz_attempt(request, pk):
    attempt = get_object_or_404(QuizAttempt.objects.select_related('quiz'), pk=pk, student=request.user, finished_at__isnull=True)
    return render(request, 'quiz_module/attempt.html', {'attempt': attempt, 'questions': attempt.quiz.questions.prefetch_related('choices').all()})


@login_required
def quiz_submit(request, pk):
    attempt = get_object_or_404(QuizAttempt, pk=pk, student=request.user, finished_at__isnull=True)
    if request.method == 'POST':
        score = Decimal('0'); correct = answered = 0
        for q in attempt.quiz.questions.all():
            choice_id = request.POST.get(f'q_{q.pk}'); choice = q.choices.filter(pk=choice_id).first() if choice_id else None
            earned = q.points if choice and choice.is_correct else Decimal('0'); score += earned; answered += bool(choice); correct += bool(choice and choice.is_correct)
            QuizAnswer.objects.update_or_create(attempt=attempt, question=q, defaults={'choice': choice, 'points_earned': earned})
        attempt.score = score; attempt.correct_count = correct; attempt.answered_count = answered; attempt.finished_at = timezone.now(); attempt.save(); return redirect('quiz_module:reports')
    return redirect('quiz_module:attempt', pk)


@login_required
def quiz_reports(request):
    attempts = QuizAttempt.objects.select_related('quiz','student').order_by('-started_at')
    if request.user.role == UserRole.STUDENT: attempts = attempts.filter(student=request.user)
    return render(request, 'quiz_module/reports.html', {'attempts': attempts, 'stats': attempts.aggregate(total=Count('id'), average=Avg('score'))})
