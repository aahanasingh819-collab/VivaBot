from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class VivaSession(models.Model):
    class Status(models.TextChoices):
        GENERATED = "generated", "Generated"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"

    class Difficulty(models.TextChoices):
        EASY = "easy", "Easy"
        MEDIUM = "medium", "Medium"
        CHALLENGING = "challenging", "Challenging"

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="viva_sessions"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="viva_sessions"
    )
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.GENERATED
    )
    difficulty = models.CharField(
        max_length=16, choices=Difficulty.choices, default=Difficulty.MEDIUM
    )
    total_questions = models.PositiveSmallIntegerField(default=10)
    current_question_number = models.PositiveSmallIntegerField(default=1)
    overall_score = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.project.title} viva ({self.get_status_display()})"


class Question(models.Model):
    class Category(models.TextChoices):
        OBJECTIVE = "objective", "Project objective"
        PROBLEM = "problem", "Problem statement"
        USERS = "users", "Target users"
        ARCHITECTURE = "architecture", "Architecture"
        TECHNOLOGY = "technology", "Technology"
        API = "api", "API design"
        DATABASE = "database", "Database"
        IMPLEMENTATION = "implementation", "Implementation"
        ALGORITHMS = "algorithms", "Algorithms and logic"
        SECURITY = "security", "Authentication and security"
        TESTING = "testing", "Testing"
        CHALLENGES = "challenges", "Challenges"
        SCALABILITY = "scalability", "Scalability"
        LIMITATIONS = "limitations", "Limitations"
        FUTURE = "future", "Future improvements"

    class Difficulty(models.TextChoices):
        EASY = "easy", "Easy"
        MEDIUM = "medium", "Medium"
        CHALLENGING = "challenging", "Challenging"

    viva_session = models.ForeignKey(
        VivaSession, on_delete=models.CASCADE, related_name="questions"
    )
    question_text = models.CharField(max_length=700)
    category = models.CharField(max_length=24, choices=Category.choices)
    order = models.PositiveSmallIntegerField()
    difficulty = models.CharField(max_length=16, choices=Difficulty.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["viva_session", "order"], name="unique_question_order_per_viva"
            )
        ]

    def __str__(self):
        return f"Q{self.order}: {self.question_text[:70]}"


class Answer(models.Model):
    question = models.OneToOneField(
        Question, on_delete=models.CASCADE, related_name="answer"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="answers"
    )
    answer_text = models.TextField(max_length=5000)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["submitted_at"]

    def __str__(self):
        return f"Answer by {self.user} for {self.question}"


class Evaluation(models.Model):
    answer = models.OneToOneField(
        Answer, on_delete=models.CASCADE, related_name="evaluation"
    )
    score = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
    )
    feedback = models.TextField()
    strengths = models.JSONField(default=list)
    missing_points = models.JSONField(default=list)
    suggested_answer = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.score}/10 — {self.answer.question}"