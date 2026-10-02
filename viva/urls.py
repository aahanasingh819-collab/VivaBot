from django.urls import path

from viva.views import generate, next_question, results, session_detail, submit_answer

app_name = "viva"

urlpatterns = [
    path(
        "projects/<int:project_id>/generate-viva/",
        generate,
        name="generate",
    ),
    path("viva/<int:session_id>/", session_detail, name="session"),
    path(
        "viva/<int:session_id>/questions/<int:question_id>/answer/",
        submit_answer,
        name="submit_answer",
    ),
    path("viva/<int:session_id>/next/", next_question, name="next"),
    path("viva/<int:session_id>/results/", results, name="results"),
]