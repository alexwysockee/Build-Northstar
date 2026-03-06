from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseForbidden
from django.utils import timezone

from django.views.decorators.http import require_POST

from .forms import UserGroupsForm, UserAddForm, ProfilePictureForm, UserSetPasswordForm
from .models import UserProfile


def _can_see_users(user):
    """True if user is staff (admin), Management, or Back Office."""
    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    return user.groups.filter(name__in=["Management", "Back Office"]).exists()


def _last_login_css_class(user):
    """Return CSS class for last_login: recent (green), within 24h (yellow), older."""
    if user.last_login is None:
        return "last-login-never"
    now = timezone.now()
    delta_seconds = (now - user.last_login).total_seconds()
    if delta_seconds < 3600:  # within 1 hour
        return "last-login-recent"
    if delta_seconds < 24 * 3600:  # within 24 hours
        return "last-login-24h"
    return "last-login-old"


def _is_protected_admin_account(user_obj: User) -> bool:
    """True if this is the built-in admin account we never allow modifying/removing."""
    # Protect the main admin account and any superuser accounts.
    return bool(user_obj.is_superuser or user_obj.username.lower() == "admin")


def user_list(request):
    """List all users. Only staff, Management, Back Office can access."""
    if not _can_see_users(request.user):
        return HttpResponseForbidden("You don't have permission to view users.")
    users = User.objects.all().order_by("username").prefetch_related("groups")
    profiles = UserProfile.objects.filter(user__in=users).select_related("user")
    avatar_by_user_id = {p.user_id: (p.avatar.url if p.avatar else None) for p in profiles}
    users_with_login = [(u, _last_login_css_class(u), avatar_by_user_id.get(u.id)) for u in users]
    context = {
        "users_with_login": users_with_login,
        "can_see_users": True,
        "can_modify_user_groups": _can_see_users(request.user),
    }
    return render(request, "Profile/users.html", context)


def user_add(request):
    """Add a new user. Only staff, Management, Back Office."""
    if not _can_see_users(request.user):
        return HttpResponseForbidden("You don't have permission to add users.")
    if request.method == "POST":
        form = UserAddForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("Profile:user_list")
        context = {"form": form}
        return render(request, "Profile/user_add.html", context)
    return render(request, "Profile/user_add.html", {"form": UserAddForm()})


@require_POST
def user_delete(request, user_id):
    """Remove a user. Only staff, Management, Back Office. Cannot delete yourself."""
    if not _can_see_users(request.user):
        return HttpResponseForbidden("You don't have permission to remove users.")
    target = get_object_or_404(User, pk=user_id)
    if _is_protected_admin_account(target):
        return HttpResponseForbidden("The admin account cannot be removed.")
    if target.pk == request.user.pk:
        return HttpResponseForbidden("You cannot remove your own account.")
    target.delete()
    return redirect("Profile:user_list")


def user_edit_groups(request, user_id):
    """Edit a user's groups. Only staff and Management can access."""
    if not _can_see_users(request.user):
        return HttpResponseForbidden("You don't have permission to edit user groups.")
    edit_user = get_object_or_404(User, pk=user_id)
    if request.method == "POST":
        form = UserGroupsForm(user=edit_user, data=request.POST)
        if form.is_valid():
            form.save()
            return redirect("Profile:user_list")
    else:
        form = UserGroupsForm(user=edit_user)
    context = {"form": form, "edit_user": edit_user}
    return render(request, "Profile/user_edit_groups.html", context)


def user_set_password(request, user_id):
    """Set a user's password (cannot display existing password)."""
    if not _can_see_users(request.user):
        return HttpResponseForbidden("You don't have permission to set passwords.")
    target = get_object_or_404(User, pk=user_id)
    if _is_protected_admin_account(target):
        return HttpResponseForbidden("The admin account password cannot be changed here.")
    if request.method == "POST":
        form = UserSetPasswordForm(request.POST)
        if form.is_valid():
            target.set_password(form.cleaned_data["password1"])
            target.save()
            return redirect("Profile:user_list")
    else:
        form = UserSetPasswordForm()
    return render(request, "Profile/user_set_password.html", {"target": target, "form": form})


def profile(request):
    """Logged-in user's profile page (avatar upload)."""
    if not request.user.is_authenticated:
        return HttpResponseForbidden("You must be logged in.")

    prof, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = ProfilePictureForm(request.POST, request.FILES)
        if form.is_valid():
            avatar = form.cleaned_data.get("avatar")
            if avatar:
                # Replace old avatar file
                if prof.avatar:
                    prof.avatar.delete(save=False)
                prof.avatar = avatar
                prof.save()
            return redirect("Profile:profile")
    else:
        form = ProfilePictureForm()

    context = {"profile": prof, "form": form}
    return render(request, "Profile/profile.html", context)
