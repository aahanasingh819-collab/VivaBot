from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import IsOwnerObjectPermission
from api.serializers import (
    ProjectSerializer,
    SubmitAnswerSerializer,
    VivaSessionSerializer,
)
from projects.models import Project
from viva.models import Question, VivaSession
from viva.services.gemini_service import GeminiServiceError
from viva.services.viva_service import generate_viva, record_answer


class ProjectViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated, IsOwnerObjectPermission]

    def get_queryset(self):
        return Project.objects.filter(user=self.request.user)

    @action(detail=True, methods=["post"], url_path="vivas")
    def vivas(self, request, pk=None):
        project = self.get_object()
        difficulty = request.data.get("difficulty", VivaSession.Difficulty.MEDIUM)
        if difficulty not in dict(VivaSession.Difficulty.choices):
            return Response(
                {"difficulty": ["Choose easy, medium, or challenging."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            session = generate_viva(project, request.user, difficulty)
        except GeminiServiceError as exc:
            return Response(
                {"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        serializer = VivaSessionSerializer(session, context={"request": request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class VivaSessionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = VivaSessionSerializer
    permission_classes = [IsAuthenticated, IsOwnerObjectPermission]

    def get_queryset(self):
        return (
            VivaSession.objects.filter(user=self.request.user)
            .select_related("project")
            .prefetch_related("questions__answer__evaluation")
        )

    @action(detail=True, methods=["get"], url_path="result")
    def result(self, request, pk=None):
        session = self.get_object()
        if session.status != VivaSession.Status.COMPLETED:
            return Response(
                {"detail": "Results are available when the viva is complete."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(self.get_serializer(session).data)


class QuestionAnswerView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, question_id):
        question = get_object_or_404(
            Question.objects.select_related("viva_session__project").filter(
                viva_session__user=request.user
            ),
            pk=question_id,
        )
        serializer = SubmitAnswerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            answer = record_answer(
                question, request.user, serializer.validated_data["answer_text"]
            )
        except DjangoValidationError as exc:
            return Response(
                {"detail": exc.messages[0]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except GeminiServiceError as exc:
            return Response(
                {"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        session_serializer = VivaSessionSerializer(
            question.viva_session, context={"request": request}
        )
        answer_data = next(
            item["answer"]
            for item in session_serializer.data["questions"]
            if item["id"] == question.id
        )
        return Response(answer_data, status=status.HTTP_200_OK)