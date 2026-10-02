from django.contrib.auth import views as auth_views
from django.urls import path

from users.views import landing, profile, register, sign_in

app_name = "users"

urlpatterns = [
    path("", landing, name="landing"),
    path("register/", register, name="register"),
    path("login/", sign_in, name="login"),
    path(
        "logout/",
        auth_views.LogoutView.as_view(next_page="users:landing"),
        name="logout",
    ),
    path("profile/", profile, name="profile"),
]