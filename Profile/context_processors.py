def profile_context(request):
    """Add can_see_users, can_modify_daily_sales, and profile avatar for templates."""
    can_see_users = False
    can_modify_daily_sales = False
    profile_avatar_url = None
    if request.user.is_authenticated:
        can_see_users = request.user.is_staff or request.user.groups.filter(
            name__in=["Management", "Back Office"]
        ).exists()
        # Admin, Sales Rep, or Dealership User can add/edit/delete daily sales
        group_names = {g.name for g in request.user.groups.all()}
        can_modify_daily_sales = (
            request.user.is_staff
            or "Sales Rep" in group_names
            or "Dealership User" in group_names
        )
        try:
            from .models import UserProfile

            prof = UserProfile.objects.filter(user=request.user).first()
            if prof and prof.avatar:
                profile_avatar_url = prof.avatar.url
        except Exception:
            profile_avatar_url = None
    return {
        "can_see_users": can_see_users,
        "can_modify_daily_sales": can_modify_daily_sales,
        "profile_avatar_url": profile_avatar_url,
    }
