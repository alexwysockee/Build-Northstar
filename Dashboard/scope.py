"""Who may see company-wide (all dealerships) data vs a single home dealership."""

from django.contrib.auth import get_user_model


def user_can_view_all_dealerships(user) -> bool:
    if not user.is_authenticated:
        return False
    # Read flags and groups from the DB so we are not fooled by a stale session user
    # (e.g. superuser checked in admin but old request.user still in memory).
    u = (
        get_user_model()
        .objects.filter(pk=user.pk)
        .prefetch_related("groups")
        .first()
    )
    if not u:
        return False
    if u.is_staff or u.is_superuser:
        return True
    names = {g.name for g in u.groups.all()}
    return bool(names & {"Management", "Back Office"})
