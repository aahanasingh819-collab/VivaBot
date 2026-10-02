from django.contrib import admin

from viva.models import Answer, Evaluation, Question, VivaSession


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 0
    show_change_link = True


@admin.register(VivaSession)
class VivaSessionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "project",
        "user",
        "status",
        "difficulty",
        "overall_score",
        "created_at",
    )
    list_filter = ("status", "difficulty", "created_at")
    search_fields = ("project__title", "user__username")
    inlines = [QuestionInline]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("id", "viva_session", "order", "category", "difficulty")
    list_filter = ("category", "difficulty")
    search_fields = ("question_text", "viva_session__project__title")


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ("id", "question", "user", "submitted_at")
    search_fields = ("answer_text", "user__username")


@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = ("id", "answer", "score", "created_at")
    list_filter = ("score", "created_at")
    search_fields = ("feedback", "suggested_answer")