def profile_context(request):
    """Add can_see_users so base template can show Users link only to admin/Management."""
    can_see_users = False
    if request.user.is_authenticated:
        can_see_users = request.user.is_staff or request.user.groups.filter(
            name="Management"
        ).exists()
    return {"can_see_users": can_see_users}
