from django.core.exceptions import ValidationError as DjangoValidationError
from django.urls import reverse
from rest_framework import serializers

from projects.models import Project
from projects.services.document_parser import DocumentExtractionError, extract_report_text
from projects.validators import validate_report_upload
from viva.models import Answer, Evaluation, Question, VivaSession


class ProjectSerializer(serializers.ModelSerializer):
    report_file = serializers.FileField(write_only=True, required=False)
    report_filename = serializers.CharField(read_only=True)
    report_download_url = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = (
            "id",
            "title",
            "description",
            "technologies_used",
            "report_file",
            "report_filename",
            "report_download_url",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_report_file(self, upload):
        try:
            validate_report_upload(upload)
            text = extract_report_text(upload)
        except (DjangoValidationError, DocumentExtractionError) as exc:
            detail = exc.messages if hasattr(exc, "messages") else str(exc)
            raise serializers.ValidationError(detail) from exc
        upload.seek(0)
        self._extracted_text = text
        return upload

    def validate(self, attrs):
        if not self.instance and "report_file" not in attrs:
            raise serializers.ValidationError(
                {"report_file": "Choose a project report to upload."}
            )
        return attrs

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        validated_data["extracted_text"] = self._extracted_text
        return Project.objects.create(**validated_data)

    def update(self, instance, validated_data):
        upload = validated_data.pop("report_file", None)
        old_file = instance.report_file
        for field, value in validated_data.items():
            setattr(instance, field, value)
        if upload is not None:
            instance.report_file = upload
            instance.extracted_text = self._extracted_text
        instance.save()
        if upload is not None and old_file.name != instance.report_file.name:
            old_file.delete(save=False)
        return instance

    def get_report_download_url(self, obj):
        request = self.context.get("request")
        url = reverse("projects:download_report", kwargs={"project_id": obj.pk})
        return request.build_absolute_uri(url) if request else url


class EvaluationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Evaluation
        fields = (
            "score",
            "feedback",
            "strengths",
            "missing_points",
            "suggested_answer",
            "created_at",
        )
        read_only_fields = fields


class AnswerSerializer(serializers.ModelSerializer):
    evaluation = EvaluationSerializer(read_only=True)

    class Meta:
        model = Answer
        fields = ("answer_text", "submitted_at", "evaluation")
        read_only_fields = fields


class QuestionSerializer(serializers.ModelSerializer):
    answer = AnswerSerializer(read_only=True)

    class Meta:
        model = Question
        fields = (
            "id",
            "question_text",
            "category",
            "order",
            "difficulty",
            "answer",
        )
        read_only_fields = fields


class VivaSessionSerializer(serializers.ModelSerializer):
    project_title = serializers.CharField(source="project.title", read_only=True)
    questions = QuestionSerializer(many=True, read_only=True)

    class Meta:
        model = VivaSession
        fields = (
            "id",
            "project",
            "project_title",
            "status",
            "difficulty",
            "total_questions",
            "current_question_number",
            "overall_score",
            "started_at",
            "completed_at",
            "created_at",
            "questions",
        )
        read_only_fields = fields


class SubmitAnswerSerializer(serializers.Serializer):
    answer_text = serializers.CharField(
        max_length=5000, allow_blank=False, trim_whitespace=True
    )

    def validate_answer_text(self, value):
        if not value.strip():
            raise serializers.ValidationError("Write an answer before submitting.")
        return value.strip()