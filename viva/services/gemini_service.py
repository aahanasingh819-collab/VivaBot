import json
import logging
import re

from django.conf import settings
from google import genai
from google.genai import types

from viva.models import Question

logger = logging.getLogger(__name__)

MAX_CONTEXT_CHARS = 28_000
MAX_ANSWER_CHARS = 5_000
QUESTION_COUNT = 10


class GeminiServiceError(RuntimeError):
    """Safe, user-presentable failure from Gemini."""


class GeminiConfigurationError(GeminiServiceError):
    """Raised when server-side Gemini credentials are not configured."""


def _bounded_context(text):
    text = (text or "").strip()
    if len(text) <= MAX_CONTEXT_CHARS:
        return text
    marker = "\n\n[Middle of the report omitted to fit the safe context limit.]\n\n"
    budget = MAX_CONTEXT_CHARS - len(marker)
    beginning = int(budget * 0.78)
    ending = budget - beginning
    return text[:beginning] + marker + text[-ending:]


def _client():
    if not settings.GOOGLE_API_KEY:
        raise GeminiConfigurationError(
            "Gemini is not configured yet. Add GOOGLE_API_KEY to the server's environment."
        )
    return genai.Client(api_key=settings.GOOGLE_API_KEY)


def _json_response(prompt):
    try:
        with _client() as client:
            response = client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.35,
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(
                        disable=True
                    ),
                ),
            )
    except GeminiConfigurationError:
        raise
    except Exception as exc:
        logger.exception(
            "Gemini request failed: %s: %s",
            type(exc).__name__,
            exc,
        )
        raise GeminiServiceError(
            "Gemini could not complete this request. Please try again in a moment."
        ) from exc

    content = getattr(response, "text", None)
    if not content:
        raise GeminiServiceError("Gemini returned an empty response. Please try again.")
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.IGNORECASE)
    try:
        return json.loads(content)
    except (json.JSONDecodeError, TypeError) as exc:
        raise GeminiServiceError(
            "Gemini returned a response we couldn't validate. Please try again."
        ) from exc


def _required_string(value, field, limit=3000):
    if not isinstance(value, str) or not value.strip():
        raise GeminiServiceError(f"Gemini's {field} response was incomplete. Please retry.")
    return value.strip()[:limit]


def generate_questions(project, difficulty="medium"):
    """Generate validated, project-grounded questions without persisting partial output."""
    difficulty = (
        difficulty
        if difficulty in dict(Question.Difficulty.choices)
        else Question.Difficulty.MEDIUM
    )
    prompt = f"""
You are a fair college project viva examiner. Generate exactly {QUESTION_COUNT}
viva questions based only on the project details and report below. Do not invent
features, systems, or implementation choices. Ask about a topic only when the
report supports it. Cover a balanced range of relevant areas and vary question
difficulty. Be specific enough that the student must understand their project.
Return one JSON object with a "questions" array. Every array item must contain:
"question_text" (one clear question), "category" (one of the allowed keys),
and "difficulty" (easy, medium, or challenging). No markdown or additional keys.
Allowed category keys: {", ".join(Question.Category.values)}.
Overall requested difficulty: {difficulty}.

Project name: {project.title}
Project description: {project.description}
Technologies listed by student: {project.technologies_used or "Not specified"}
Extracted report:
{_bounded_context(project.extracted_text)}
"""
    payload = _json_response(prompt)
    values = payload.get("questions") if isinstance(payload, dict) else None
    if not isinstance(values, list) or not 8 <= len(values) <= 12:
        raise GeminiServiceError(
            "Gemini didn't return 8–12 usable questions. Please generate the viva again."
        )

    valid_categories = set(Question.Category.values)
    valid_difficulties = set(Question.Difficulty.values)
    clean = []
    seen = set()
    for item in values:
        if not isinstance(item, dict):
            raise GeminiServiceError("Gemini returned a malformed question. Please retry.")
        text = item.get("question_text")
        category = item.get("category")
        level = item.get("difficulty")
        if (
            not isinstance(text, str)
            or not text.strip()
            or len(text) > 700
            or category not in valid_categories
            or level not in valid_difficulties
        ):
            raise GeminiServiceError("Gemini returned a malformed question. Please retry.")
        text = text.strip()
        normalized = text.casefold()
        if normalized in seen:
            raise GeminiServiceError("Gemini returned duplicate questions. Please retry.")
        seen.add(normalized)
        clean.append(
            {
                "question_text": text,
                "category": category,
                "difficulty": level,
            }
        )
    return clean


def evaluate_answer(project, question, answer_text):
    """Return a strict, bounded evaluation tied to the actual project context."""
    answer_text = answer_text.strip()
    if not answer_text:
        raise ValueError("Write an answer before submitting.")
    if len(answer_text) > MAX_ANSWER_CHARS:
        raise ValueError("Answers must be 5,000 characters or fewer.")

    prompt = f"""
You are a supportive college project viva examiner. Evaluate the student's
answer for correctness, relevance to the question, completeness, technical
understanding, and clarity. Use only the report as project facts. Be fair and
specific; do not insult the student or claim the evaluation is objectively
certain. Award an integer score from 0 to 10. Return a single JSON object with:
"score" (integer 0–10), "feedback" (concise explanation), "strengths" (array of
short strings), "missing_points" (array of short strings), and
"suggested_answer" (a technically accurate sample answer grounded in the report).
No markdown or extra keys.

Project: {project.title}
Project description: {project.description}
Technologies: {project.technologies_used or "Not specified"}
Report context:
{_bounded_context(project.extracted_text)}

Question ({question.get_category_display()}): {question.question_text}
Student answer:
{answer_text}
"""
    payload = _json_response(prompt)
    if not isinstance(payload, dict):
        raise GeminiServiceError("Gemini's evaluation was malformed. Please try again.")
    score = payload.get("score")
    if isinstance(score, bool) or not isinstance(score, (int, float)) or not 0 <= score <= 10:
        raise GeminiServiceError("Gemini's score was outside 0–10. Please try again.")

    def string_list(value, name):
        if not isinstance(value, list) or any(
            not isinstance(item, str) or not item.strip() for item in value
        ):
            raise GeminiServiceError(f"Gemini's {name} response was malformed. Please retry.")
        return [item.strip()[:400] for item in value[:6]]

    return {
        "score": round(float(score), 2),
        "feedback": _required_string(payload.get("feedback"), "feedback", 2000),
        "strengths": string_list(payload.get("strengths"), "strengths"),
        "missing_points": string_list(payload.get("missing_points"), "missing points"),
        "suggested_answer": _required_string(
            payload.get("suggested_answer"), "suggested answer", 3000
        ),
    }