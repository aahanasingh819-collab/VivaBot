from django import forms
from django.core.exceptions import ValidationError

from projects.models import Project
from projects.services.document_parser import DocumentExtractionError, extract_report_text
from projects.validators import validate_report_upload


class ProjectForm(forms.ModelForm):
    report_file = forms.FileField(
        required=False,
        help_text="PDF, DOCX, or TXT · up to 10 MB",
    )

    class Meta:
        model = Project
        fields = ("title", "description", "technologies_used", "report_file")
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "e.g. Campus Queue Manager"}),
            "description": forms.Textarea(
                attrs={"rows": 3, "placeholder": "What does your project help people do?"}
            ),
            "technologies_used": forms.TextInput(
                attrs={"placeholder": "Python, Django, PostgreSQL"}
            ),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        self.fields["report_file"].required = self.instance.pk is None
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
        self.fields["report_file"].widget.attrs.update(
            {"accept": ".pdf,.txt,.docx", "class": "file-input"}
        )

    def clean_report_file(self):
        upload = self.cleaned_data.get("report_file")
        if not upload:
            if self.instance.pk:
                return None
            raise ValidationError("Choose a project report to upload.")
        validate_report_upload(upload)
        try:
            self.extracted_text = extract_report_text(upload)
        except DocumentExtractionError as exc:
            raise ValidationError(str(exc)) from exc
        upload.seek(0)
        return upload

    def save(self, commit=True):
        project = super().save(commit=False)
        if self.user:
            project.user = self.user
        upload = self.cleaned_data.get("report_file")
        if upload:
            project.extracted_text = self.extracted_text
        if commit:
            project.save()
            self.save_m2m()
        return project