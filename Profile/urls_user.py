"""User management URLs (mounted at /home/users/)."""
from django.urls import path

from . import views

urlpatterns = [
    path("", views.user_list, name="user_list"),
    path("add/", views.user_add, name="user_add"),
    path("<int:user_id>/groups/", views.user_edit_groups, name="user_edit_groups"),
    path("<int:user_id>/password/", views.user_set_password, name="user_set_password"),
    path("<int:user_id>/delete/", views.user_delete, name="user_delete"),
]
