from django.urls import path

from projects.views import (
    dashboard,
    download_report,
    history,
    project_create,
    project_delete,
    project_detail,
    project_edit,
)

app_name = "projects"

urlpatterns = [
    path("dashboard/", dashboard, name="dashboard"),
    path("projects/new/", project_create, name="create"),
    path("projects/<int:project_id>/", project_detail, name="detail"),
    path("projects/<int:project_id>/edit/", project_edit, name="edit"),
    path("projects/<int:project_id>/delete/", project_delete, name="delete"),
    path("projects/<int:project_id>/report/", download_report, name="download_report"),
    path("history/", history, name="history"),
]