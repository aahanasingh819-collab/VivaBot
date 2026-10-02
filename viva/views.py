from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg
from django.core.exceptions import ValidationError
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from projects.models import Project
from viva.models import Answer, Question, VivaSession
from viva.services.gemini_service import GeminiServiceError
from viva.services.viva_service import (
    advance_viva,
    generate_viva,
    record_answer,
    start_viva,
)


@login_required
@require_POST
def generate(request, project_id):
    project = get_object_or_404(Project, pk=project_id, user=request.user)
    difficulty = request.POST.get("difficulty", VivaSession.Difficulty.MEDIUM)
    if difficulty not in dict(VivaSession.Difficulty.choices):
        difficulty = VivaSession.Difficulty.MEDIUM
    try:
        session = generate_viva(project, request.user, difficulty)
    except GeminiServiceError as exc:
        messages.error(request, str(exc))
        return redirect("projects:detail", project_id=project.pk)
    except Exception:
        messages.error(
            request,
            "Your viva could not be created right now. Please try again.",
        )
        return redirect("projects:detail", project_id=project.pk)
    return redirect("viva:session", session_id=session.pk)


@login_required
def session_detail(request, session_id):
    session = get_object_or_404(
        VivaSession.objects.select_related("project").filter(user=request.user),
        pk=session_id,
    )
    if session.status == VivaSession.Status.COMPLETED:
        return redirect("viva:results", session_id=session.pk)
    try:
        session = start_viva(session, request.user)
    except ValidationError:
        return redirect("projects:dashboard")
    question = session.questions.filter(order=session.current_question_number).first()
    answer = None
    if question:
        answer = (
            Answer.objects.filter(question=question, user=request.user)
            .select_related("evaluation")
            .first()
        )
    return render(
        request,
        "viva/session.html",
        {"session": session, "question": question, "answer": answer},
    )


@login_required
@require_POST
def submit_answer(request, session_id, question_id):
    session = get_object_or_404(VivaSession, pk=session_id, user=request.user)
    question = get_object_or_404(
        Question, pk=question_id, viva_session=session
    )
    try:
        record_answer(question, request.user, request.POST.get("answer_text", ""))
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
    except GeminiServiceError as exc:
        messages.error(request, str(exc))
    except Exception:
        messages.error(request, "We couldn't evaluate that answer. Please try again.")
    return redirect("viva:session", session_id=session.pk)


@login_required
@require_POST
def next_question(request, session_id):
    session = get_object_or_404(VivaSession, pk=session_id, user=request.user)
    try:
        session = advance_viva(session, request.user)
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
        return redirect("viva:session", session_id=session.pk)
    if session.status == VivaSession.Status.COMPLETED:
        return redirect("viva:results", session_id=session.pk)
    return redirect("viva:session", session_id=session.pk)


@login_required
def results(request, session_id):
    session = get_object_or_404(
        VivaSession.objects.select_related("project").filter(user=request.user),
        pk=session_id,
    )
    if session.status != VivaSession.Status.COMPLETED:
        return redirect("viva:session", session_id=session.pk)
    question_queryset = Question.objects.select_related("answer__evaluation")
    session = (
        VivaSession.objects.select_related("project")
        .prefetch_related(Prefetch("questions", queryset=question_queryset))
        .get(pk=session.pk, user=request.user)
    )
    grouped = {}
    for row in session.questions.values("category").annotate(
        score=Avg("answer__evaluation__score")
    ):
        if row["score"] is not None:
            grouped[row["category"]] = row["score"]
    labels = dict(Question.Category.choices)
    ranked = [
        {"label": labels.get(category, category), "score": score}
        for category, score in grouped.items()
    ]
    return render(
        request,
        "viva/results.html",
        {
            "session": session,
            "strongest_areas": sorted(
                ranked, key=lambda item: item["score"], reverse=True
            )[:3],
            "growth_areas": sorted(ranked, key=lambda item: item["score"])[:3],
            "score_percentage": round(float(session.overall_score or 0) * 10),
        },
    )