from decimal import Decimal
from io import BytesIO
import json
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from docx import Document
from projects.models import Project
from viva.models import Question, VivaSession

User = get_user_model()


def make_project(user, title="Queue Manager"):
    return Project.objects.create(
        user=user,
        title=title,
        description="A queue management tool for campus services.",
        technologies_used="Python, Django",
        extracted_text=(
            "The system assigns a unique queue number when a student requests service. "
            "Staff update the queue from a Django dashboard."
        ),
    )


def make_questions():
    categories = [
        Question.Category.OBJECTIVE,
        Question.Category.PROBLEM,
        Question.Category.USERS,
        Question.Category.ARCHITECTURE,
        Question.Category.TECHNOLOGY,
        Question.Category.DATABASE,
        Question.Category.IMPLEMENTATION,
        Question.Category.TESTING,
    ]
    return [
        {
            "question_text": f"How does your project address topic {index}?",
            "category": category,
            "difficulty": Question.Difficulty.MEDIUM,
        }
        for index, category in enumerate(categories, start=1)
    ]


EVALUATION = {
    "score": 7.5,
    "feedback": "You explained the unique queue number clearly. Add how duplicate requests are handled.",
    "strengths": ["Explained the core workflow."],
    "missing_points": ["Describe duplicate request handling."],
    "suggested_answer": "A request receives a unique queue number, which staff update from the dashboard.",
}


class OwnershipApiTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner", password="Strong-pass-934!")
        self.other = User.objects.create_user("other", password="Strong-pass-934!")
        self.project = make_project(self.owner)
        self.session = VivaSession.objects.create(
            user=self.owner,
            project=self.project,
            status=VivaSession.Status.IN_PROGRESS,
            total_questions=1,
            current_question_number=1,
        )
        self.question = Question.objects.create(
            viva_session=self.session,
            question_text="Why does the system assign a unique number?",
            category=Question.Category.IMPLEMENTATION,
            order=1,
            difficulty=Question.Difficulty.MEDIUM,
        )

    def test_anonymous_user_is_redirected_from_private_pages(self):
        response = self.client.get(reverse("projects:detail", args=[self.project.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response["Location"])

    def test_another_user_cannot_read_project_report_or_viva(self):
        self.client.force_login(self.other)
        project_response = self.client.get(
            reverse("projects:detail", args=[self.project.pk])
        )
        viva_response = self.client.get(
            reverse("viva:session", args=[self.session.pk])
        )
        report_response = self.client.get(
            reverse("projects:download_report", args=[self.project.pk])
        )
        self.assertEqual(project_response.status_code, 404)
        self.assertEqual(viva_response.status_code, 404)
        self.assertEqual(report_response.status_code, 404)

    def test_api_hides_another_users_project_and_viva(self):
        self.client.force_login(self.other)
        project_response = self.client.get(f"/vivabot-api/projects/{self.project.pk}/")
        viva_response = self.client.get(f"/vivabot-api/vivas/{self.session.pk}/")
        self.assertEqual(project_response.status_code, 404)
        self.assertEqual(viva_response.status_code, 404)

    def test_api_project_list_only_returns_the_signed_in_users_projects(self):
        make_project(self.other, "Other student's app")
        self.client.force_login(self.owner)
        response = self.client.get("/vivabot-api/projects/")
        self.assertEqual(response.status_code, 200)
        titles = [item["title"] for item in response.json()["results"]]
        self.assertEqual(titles, [self.project.title])

    def test_api_rejects_blank_answers(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            f"/vivabot-api/questions/{self.question.pk}/answer/",
            {"answer_text": "   "},
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(hasattr(self.question, "answer"))

    def test_api_can_submit_answer_and_return_its_evaluation(self):
        from unittest.mock import patch

        self.client.force_login(self.owner)
        with patch(
            "viva.services.viva_service.evaluate_answer", return_value=EVALUATION
        ):
            response = self.client.post(
                f"/vivabot-api/questions/{self.question.pk}/answer/",
                data=json.dumps({"answer_text": "Each request receives a unique number."}),
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["answer_text"], "Each request receives a unique number."
        )
        self.assertEqual(response.json()["evaluation"]["score"], "7.50")

    def test_api_can_generate_a_viva_and_returns_conflict_until_completed(self):
        from unittest.mock import patch

        self.client.force_login(self.owner)
        with patch("api.views.generate_viva", return_value=self.session):
            response = self.client.post(
                f"/vivabot-api/projects/{self.project.pk}/vivas/",
                data=json.dumps({"difficulty": "medium"}),
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["id"], self.session.pk)
        self.assertEqual(len(response.json()["questions"]), 1)
        incomplete_result = self.client.get(f"/vivabot-api/vivas/{self.session.pk}/result/")
        self.assertEqual(incomplete_result.status_code, 409)

        self.session.status = VivaSession.Status.COMPLETED
        self.session.overall_score = Decimal("8.00")
        self.session.save()
        completed_result = self.client.get(f"/vivabot-api/vivas/{self.session.pk}/result/")
        self.assertEqual(completed_result.status_code, 200)
        self.assertEqual(completed_result.json()["overall_score"], "8.00")

    def test_api_answer_for_foreign_question_is_not_found(self):
        self.client.force_login(self.other)
        response = self.client.post(
            f"/vivabot-api/questions/{self.question.pk}/answer/",
            {"answer_text": "A reasoned response."},
        )
        self.assertEqual(response.status_code, 404)


class ProjectUploadTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("student", password="Strong-pass-934!")
        self.client.force_login(self.user)

    def test_txt_report_is_extracted_and_persisted(self):
        response = self.client.post(
            reverse("projects:create"),
            {
                "title": "Accessible Study Planner",
                "description": "A planner for students who need flexible reminders.",
                "technologies_used": "Django, SQLite",
                "report_file": SimpleUploadedFile(
                    "planner.txt",
                    b"The planner uses Django authentication and saves reminders in SQLite.",
                    content_type="text/plain",
                ),
            },
        )
        self.assertEqual(response.status_code, 302)
        project = Project.objects.get(title="Accessible Study Planner")
        self.assertIn("Django authentication", project.extracted_text)
        self.assertTrue(project.report_file.name.endswith(".txt"))

    def test_docx_report_is_extracted_and_persisted(self):
        document = Document()
        document.add_paragraph(
            "The study planner uses calendar reminders to help students organize tasks."
        )
        buffer = BytesIO()
        document.save(buffer)
        response = self.client.post(
            reverse("projects:create"),
            {
                "title": "Study Planner",
                "description": "A planner with reminders.",
                "technologies_used": "Django",
                "report_file": SimpleUploadedFile(
                    "planner.docx",
                    buffer.getvalue(),
                    content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ),
            },
        )
        self.assertEqual(response.status_code, 302)
        project = Project.objects.get(title="Study Planner")
        self.assertIn("calendar reminders", project.extracted_text)

    def test_unsupported_upload_is_rejected(self):
        response = self.client.post(
            reverse("projects:create"),
            {
                "title": "Unsupported report",
                "description": "This should not be saved.",
                "report_file": SimpleUploadedFile(
                    "payload.exe", b"not an executable we run", content_type="application/octet-stream"
                ),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Upload a PDF, TXT, or DOCX report.")
        self.assertFalse(Project.objects.filter(title="Unsupported report").exists())

    def test_invalid_text_encoding_is_a_form_error(self):
        response = self.client.post(
            reverse("projects:create"),
            {
                "title": "Invalid report",
                "description": "This should not be saved.",
                "report_file": SimpleUploadedFile(
                    "invalid.txt", b"\xff\xfe", content_type="text/plain"
                ),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "must use UTF-8")
        self.assertFalse(Project.objects.filter(title="Invalid report").exists())


class VivaFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("learner", password="Strong-pass-934!")
        self.client.force_login(self.user)
        self.project = make_project(self.user)

    def test_registration_creates_account_and_logs_in(self):
        self.client.logout()
        response = self.client.post(
            reverse("users:register"),
            {
                "username": "new-learner",
                "email": "learner@example.test",
                "password1": "V!vaPractice-2026-Strong",
                "password2": "V!vaPractice-2026-Strong",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("projects:dashboard"))
        self.assertTrue(User.objects.filter(username="new-learner").exists())
        self.assertIn("_auth_user_id", self.client.session)

    def test_gemini_missing_key_is_a_controlled_message(self):
        from django.test import override_settings

        with override_settings(GOOGLE_API_KEY=""):
            response = self.client.post(
                reverse("viva:generate", args=[self.project.pk])
            )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(VivaSession.objects.count(), 0)
        dashboard = self.client.get(response["Location"])
        self.assertContains(dashboard, "Gemini is not configured yet")

    def test_invalid_ai_questions_are_not_saved(self):
        from unittest.mock import patch

        with patch(
            "viva.services.gemini_service._json_response",
            return_value={"questions": [{"question_text": "incomplete response"}]},
        ):
            response = self.client.post(
                reverse("viva:generate", args=[self.project.pk])
            )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(VivaSession.objects.count(), 0)
        self.assertEqual(Question.objects.count(), 0)

    def test_answer_is_evaluated_once_and_remains_after_refresh(self):
        from unittest.mock import patch

        session = VivaSession.objects.create(
            project=self.project,
            user=self.user,
            status=VivaSession.Status.IN_PROGRESS,
            total_questions=1,
            current_question_number=1,
        )
        question = Question.objects.create(
            viva_session=session,
            question_text="How does a unique queue number help?",
            category=Question.Category.IMPLEMENTATION,
            order=1,
            difficulty=Question.Difficulty.MEDIUM,
        )
        endpoint = reverse(
            "viva:submit_answer", args=[session.pk, question.pk]
        )
        with patch(
            "viva.services.viva_service.evaluate_answer", return_value=EVALUATION
        ) as evaluate:
            response = self.client.post(
                endpoint, {"answer_text": "The unique value identifies each request."}
            )
            self.assertEqual(response.status_code, 302)
            self.client.post(
                endpoint, {"answer_text": "A duplicate submission is ignored."}
            )
        self.assertEqual(evaluate.call_count, 1)
        self.assertEqual(question.answer.answer_text, "The unique value identifies each request.")
        self.assertEqual(float(question.answer.evaluation.score), 7.5)
        refreshed = self.client.get(reverse("viva:session", args=[session.pk]))
        self.assertContains(refreshed, "The unique value identifies each request.")
        self.assertContains(refreshed, "AI-GENERATED EVALUATION")

    def test_full_viva_flow_saves_questions_answers_and_final_result(self):
        from unittest.mock import patch

        with patch(
            "viva.services.viva_service.generate_questions",
            return_value=make_questions(),
        ):
            response = self.client.post(
                reverse("viva:generate", args=[self.project.pk]),
            )
        session = VivaSession.objects.get()
        self.assertRedirects(
            response, reverse("viva:session", args=[session.pk]), fetch_redirect_response=False
        )

        with patch(
            "viva.services.viva_service.evaluate_answer", return_value=EVALUATION
        ):
            for index in range(1, session.total_questions + 1):
                question = session.questions.get(order=index)
                page = self.client.get(reverse("viva:session", args=[session.pk]))
                self.assertContains(page, f"Question <strong>{index}</strong> of")
                self.client.post(
                    reverse(
                        "viva:submit_answer",
                        args=[session.pk, question.pk],
                    ),
                    {"answer_text": f"My answer for question {index}."},
                )
                response = self.client.post(reverse("viva:next", args=[session.pk]))

        session.refresh_from_db()
        self.assertEqual(session.status, VivaSession.Status.COMPLETED)
        self.assertEqual(session.overall_score, Decimal("7.50"))
        self.assertEqual(session.questions.count(), 8)
        self.assertEqual(session.questions.filter(answer__isnull=False).count(), 8)
        self.assertRedirects(
            response,
            reverse("viva:results", args=[session.pk]),
            fetch_redirect_response=False,
        )
        results = self.client.get(reverse("viva:results", args=[session.pk]))
        self.assertContains(results, "VIVA COMPLETE")
        self.assertContains(results, "My answer for question 1.")
        self.assertContains(results, "Start another viva")
        self.assertContains(self.client.get(reverse("projects:history")), "Queue Manager")

    def test_existing_completed_viva_is_not_changed_by_opening_results(self):
        session = VivaSession.objects.create(
            project=self.project,
            user=self.user,
            status=VivaSession.Status.COMPLETED,
            overall_score=8,
            total_questions=0,
        )
        response = self.client.get(reverse("viva:results", args=[session.pk]))
        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        self.assertEqual(session.overall_score, Decimal("8.00"))