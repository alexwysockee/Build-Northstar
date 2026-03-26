from django.contrib.auth.models import User
from django.db import models
from Dashboard.models import Dealership


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    avatar = models.FileField(upload_to="avatars/", blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)
    dealership = models.ForeignKey(
        Dealership,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_users",
        help_text="Sales Rep / Dealership User home dealership for inventory scope.",
    )

    def __str__(self):
        return f"Profile for {self.user.username}"

