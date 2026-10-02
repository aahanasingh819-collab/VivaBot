from pathlib import Path

from django.core.exceptions import ValidationError

MAX_REPORT_SIZE = 10 * 1024 * 1024
ALLOWED_REPORT_EXTENSIONS = {".pdf", ".txt", ".docx"}


def validate_report_upload(upload):
    if not upload or not upload.name:
        raise ValidationError("Choose a project report to upload.")
    if upload.size <= 0:
        raise ValidationError("The selected report is empty.")
    if upload.size > MAX_REPORT_SIZE:
        raise ValidationError("Reports must be 10 MB or smaller.")
    suffix = Path(upload.name).suffix.lower()
    if suffix not in ALLOWED_REPORT_EXTENSIONS:
        raise ValidationError("Upload a PDF, TXT, or DOCX report.")
    if hasattr(upload, "seek"):
        upload.seek(0)