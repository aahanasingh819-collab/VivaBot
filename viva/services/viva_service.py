from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Avg
from django.utils import timezone

from viva.models import Answer, Evaluation, Question, VivaSession
from viva.services.gemini_service import (
    MAX_ANSWER_CHARS,
    evaluate_answer,
    generate_questions,
)


def generate_viva(project, user, difficulty=VivaSession.Difficulty.MEDIUM):
    if project.user_id != user.id:
        raise ValidationError("You don't have access to this project.")
    question_data = generate_questions(project, difficulty)
    with transaction.atomic():
        session = VivaSession.objects.create(
            project=project,
            user=user,
            difficulty=difficulty,
            total_questions=len(question_data),
            status=VivaSession.Status.GENERATED,
        )
        Question.objects.bulk_create(
            [
                Question(viva_session=session, order=index, **item)
                for index, item in enumerate(question_data, start=1)
            ]
        )
    return session


def start_viva(session, user):
    if session.user_id != user.id:
        raise ValidationError("You don't have access to this viva.")
    if session.status == VivaSession.Status.GENERATED:
        session.status = VivaSession.Status.IN_PROGRESS
        session.started_at = timezone.now()
        session.save(update_fields=["status", "started_at"])
    return session


def record_answer(question, user, answer_text):
    """Evaluate once and store the student's answer and evaluation together."""
    text = answer_text.strip()
    if not text:
        raise ValidationError("Write an answer before submitting.")
    if len(text) > MAX_ANSWER_CHARS:
        raise ValidationError("Answers must be 5,000 characters or fewer.")
    session = question.viva_session
    if session.user_id != user.id:
        raise ValidationError("You don't have access to this question.")
    if session.status != VivaSession.Status.IN_PROGRESS:
        raise ValidationError("This viva is not accepting answers.")
    if question.order != session.current_question_number:
        raise ValidationError("Open the current question to submit an answer.")

    existing = Answer.objects.filter(question=question, user=user).select_related(
        "evaluation"
    ).first()
    if existing:
        return existing

    result = evaluate_answer(session.project, question, text)
    try:
        with transaction.atomic():
            answer = Answer.objects.create(
                question=question,
                user=user,
                answer_text=text,
            )
            Evaluation.objects.create(answer=answer, **result)
        return answer
    except IntegrityError:
        # A second browser tab may have submitted while the model call was running.
        answer = Answer.objects.filter(question=question, user=user).select_related(
            "evaluation"
        ).first()
        if answer:
            return answer
        raise


def advance_viva(session, user):
    if session.user_id != user.id:
        raise ValidationError("You don't have access to this viva.")
    if session.status == VivaSession.Status.COMPLETED:
        return session
    current = session.questions.filter(order=session.current_question_number).first()
    if not current or not Answer.objects.filter(
        question=current, user=user, evaluation__isnull=False
    ).exists():
        raise ValidationError("Submit and review this answer before continuing.")

    with transaction.atomic():
        if session.current_question_number >= session.total_questions:
            score = session.questions.aggregate(value=Avg("answer__evaluation__score"))[
                "value"
            ]
            session.overall_score = Decimal(str(round(float(score or 0), 2)))
            session.status = VivaSession.Status.COMPLETED
            session.completed_at = timezone.now()
            session.save(
                update_fields=["overall_score", "status", "completed_at"]
            )
        else:
            session.current_question_number += 1
            session.save(update_fields=["current_question_number"])
    return session