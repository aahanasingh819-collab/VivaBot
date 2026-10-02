from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Prefetch
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from projects.forms import ProjectForm
from projects.models import Project
from viva.models import Answer, Evaluation, VivaSession


@login_required
def dashboard(request):
    projects = (
        Project.objects.filter(user=request.user)
        .annotate(viva_count=Count("viva_sessions"))
        .prefetch_related("viva_sessions")
    )
    sessions = VivaSession.objects.filter(user=request.user).select_related("project")
    completed = sessions.filter(status=VivaSession.Status.COMPLETED)
    summary = {
        "project_count": projects.count(),
        "completed_count": completed.count(),
        "average_score": completed.aggregate(value=Avg("overall_score"))["value"],
    }
    return render(
        request,
        "projects/dashboard.html",
        {
            "projects": projects[:4],
            "recent_sessions": sessions[:5],
            "summary": summary,
        },
    )


@login_required
def project_create(request):
    form = ProjectForm(request.POST or None, request.FILES or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        project = form.save()
        messages.success(request, "Project saved. Your report is ready for a viva.")
        return redirect("projects:detail", project_id=project.pk)
    return render(
        request,
        "projects/project_form.html",
        {"form": form, "page_title": "Add a project", "submit_label": "Save project"},
    )


@login_required
def project_detail(request, project_id):
    project = get_object_or_404(
        Project.objects.filter(user=request.user).prefetch_related("viva_sessions"),
        pk=project_id,
    )
    sessions = project.viva_sessions.filter(user=request.user)
    return render(
        request,
        "projects/project_detail.html",
        {"project": project, "sessions": sessions},
    )


@login_required
def project_edit(request, project_id):
    project = get_object_or_404(Project, pk=project_id, user=request.user)
    old_file = project.report_file
    form = ProjectForm(
        request.POST or None,
        request.FILES or None,
        instance=project,
        user=request.user,
    )
    if request.method == "POST" and form.is_valid():
        updated = form.save()
        new_file = updated.report_file
        if request.FILES.get("report_file") and old_file and old_file.name != new_file.name:
            old_file.delete(save=False)
        messages.success(request, "Project details updated.")
        return redirect("projects:detail", project_id=project.pk)
    return render(
        request,
        "projects/project_form.html",
        {"form": form, "project": project, "page_title": "Edit project", "submit_label": "Save changes"},
    )


@login_required
@require_POST
def project_delete(request, project_id):
    project = get_object_or_404(Project, pk=project_id, user=request.user)
    title = project.title
    project.delete()
    messages.success(request, f"{title} and its stored report were deleted.")
    return redirect("projects:dashboard")


@login_required
def download_report(request, project_id):
    project = get_object_or_404(Project, pk=project_id, user=request.user)
    try:
        project.report_file.open("rb")
    except (FileNotFoundError, OSError):
        raise Http404("This report is no longer available.")
    return FileResponse(
        project.report_file,
        as_attachment=True,
        filename=project.report_filename,
    )


@login_required
def history(request):
    sessions = (
        VivaSession.objects.filter(user=request.user)
        .select_related("project")
        .order_by("-created_at")
    )
    return render(request, "projects/history.html", {"sessions": sessions})