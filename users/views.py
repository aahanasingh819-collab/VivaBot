from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from users.forms import SignInForm, SignUpForm


def landing(request):
    if request.user.is_authenticated:
        return redirect("projects:dashboard")
    return render(request, "users/landing.html")


def register(request):
    if request.user.is_authenticated:
        return redirect("projects:dashboard")
    form = SignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Your account is ready. Add a project to get started.")
        return redirect("projects:dashboard")
    return render(request, "users/register.html", {"form": form})


def sign_in(request):
    if request.user.is_authenticated:
        return redirect("projects:dashboard")
    form = SignInForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        next_url = request.POST.get("next") or request.GET.get("next", "")
        if next_url and url_has_allowed_host_and_scheme(
            next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        ):
            return redirect(next_url)
        return redirect("projects:dashboard")
    return render(
        request,
        "users/login.html",
        {"form": form, "next": request.GET.get("next", "")},
    )


@login_required
def profile(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        if email:
            request.user.email = email
            request.user.save(update_fields=["email"])
            messages.success(request, "Your profile has been updated.")
        else:
            messages.error(request, "Enter a valid email address.")
    return render(request, "users/profile.html")