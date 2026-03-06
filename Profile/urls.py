from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from . import views

app_name = "Profile"

urlpatterns = [
    path("", LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", LogoutView.as_view(next_page="/"), name="logout"),
    path("users/", views.user_list, name="user_list"),
]
