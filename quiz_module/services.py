import random
from datetime import timedelta
from decimal import Decimal

from django.db import models, transaction
from django.utils import timezone

from questions_module.models import Choice, Question

from .models import QuizAttempt, QuizEvent


def create_attempt(quiz, student):
    question_ids = list(quiz.questions.values_list("id", flat=True))
    if quiz.shuffle_questions:
        random.shuffle(question_ids)
    choice_order = {}
    for question in quiz.questions.filter(question_type="MCQ").prefetch_related("choices"):
        ids = list(question.choices.values_list("id", flat=True))
        if quiz.shuffle_choices:
            random.shuffle(ids)
        choice_order[str(question.id)] = ids
    now = timezone.now()
    return QuizAttempt.objects.create(
        quiz=quiz, student=student,
        expires_at=min(now + timedelta(minutes=quiz.duration_minutes), quiz.closes_at),
        total_score=quiz.total_points, question_order=question_ids, choice_order=choice_order,
    )


@transaction.atomic
def finalize_attempt(attempt, auto=False):
    attempt = QuizAttempt.objects.select_for_update().select_related("quiz").get(pk=attempt.pk)
    if attempt.status != QuizAttempt.Status.IN_PROGRESS:
        return attempt
    quiz = attempt.quiz
    answers = {answer.question_id: answer for answer in attempt.answers.select_related("choice")}
    score = Decimal("0")
    correct = wrong = answered = 0
    has_descriptive = False
    for question in quiz.questions.prefetch_related("choices"):
        answer = answers.get(question.id)
        if not answer or not answer.is_answered:
            continue
        answered += 1
        if question.question_type == question.Type.DESCRIPTIVE:
            has_descriptive = True
            continue
        if answer.choice and answer.choice.is_correct:
            answer.points_earned = question.points
            correct += 1
        else:
            wrong += 1
            answer.points_earned = -(question.points * quiz.negative_ratio) if quiz.negative_marking else Decimal("0")
        answer.save(update_fields=["points_earned"])
        score += answer.points_earned
    attempt.score = max(score, Decimal("0"))
    attempt.correct_count, attempt.wrong_count, attempt.answered_count = correct, wrong, answered
    attempt.finished_at, attempt.auto_submitted = timezone.now(), auto
    attempt.status = QuizAttempt.Status.SUBMITTED if has_descriptive else QuizAttempt.Status.GRADED
    attempt.save()
    return attempt


def recalculate_attempt(attempt):
    attempt.score = max(sum((a.points_earned for a in attempt.answers.all()), Decimal("0")), Decimal("0"))
    pending = attempt.answers.filter(question__question_type="DES", graded_by__isnull=True).exists()
    attempt.status = QuizAttempt.Status.SUBMITTED if pending else QuizAttempt.Status.GRADED
    attempt.save(update_fields=["score", "status"])


@transaction.atomic
def enqueue_quiz_questions(quiz):
    if timezone.now() < quiz.closes_at:
        return 0
    created = 0
    items = quiz.questions.filter(source_question__isnull=True, submit_to_bank=True, bank_question__isnull=True, bank_topic__isnull=False).prefetch_related("choices")
    for item in items:
        bank_question = Question.objects.create(
            question_type=item.question_type, topic=item.bank_topic, chapter=item.bank_topic.chapter,
            text=item.text, image=item.image, explanation=item.explanation, creator=quiz.creator,
            approval_status=Question.ApprovalStatus.PENDING, is_active=True,
        )
        for choice in item.choices.all():
            Choice.objects.create(question=bank_question, text=choice.text, image=choice.image, is_correct=choice.is_correct)
        item.bank_question = bank_question
        item.save(update_fields=["bank_question"])
        created += 1
    return created


def log_tab_event(attempt, event_type):
    if event_type not in {"tab_hidden", "tab_visible"}:
        return
    QuizEvent.objects.create(attempt=attempt, event_type=event_type)
    if event_type == "tab_hidden":
        QuizAttempt.objects.filter(pk=attempt.pk).update(tab_switch_count=models.F("tab_switch_count") + 1)
