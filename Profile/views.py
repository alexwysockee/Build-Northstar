from django.contrib.auth.models import User
from django.shortcuts import render
from django.http import HttpResponseForbidden


def _can_see_users(user):
    """True if user is staff (admin) or in the Management group."""
    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    return user.groups.filter(name="Management").exists()


def user_list(request):
    """List all users (admin-style). Only staff and Management group can access."""
    if not _can_see_users(request.user):
        return HttpResponseForbidden("You don't have permission to view users.")
    users = User.objects.all().order_by("username").prefetch_related("groups")
    context = {"users": users, "can_see_users": True}
    return render(request, "Profile/users.html", context)
