from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path, include

from . import views

app_name = "Profile"

# Login/logout at root; user management under home/users/ (same namespace so reverse works everywhere).
urlpatterns = [
    path("", LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", LogoutView.as_view(next_page="/"), name="logout"),
    path("home/users/", include("Profile.urls_user")),
    path("home/profile/", views.profile, name="profile"),
]
