import uuid
from pathlib import Path

from django.conf import settings
from django.db import models


def project_report_path(instance, filename):
    suffix = Path(filename).suffix.lower()
    return f"reports/{instance.user_id}/{uuid.uuid4().hex}{suffix}"


class Project(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="projects"
    )
    title = models.CharField(max_length=160)
    description = models.TextField(max_length=1600)
    technologies_used = models.CharField(max_length=500, blank=True)
    report_file = models.FileField(upload_to=project_report_path)
    extracted_text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]

    def __str__(self):
        return self.title

    @property
    def report_filename(self):
        return Path(self.report_file.name).name if self.report_file else ""