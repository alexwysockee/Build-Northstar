from __future__ import annotations

from django.http import HttpResponseForbidden

from Dashboard.inventory_services import user_home_dealership
from Dashboard.scope import user_can_view_all_dealerships


class SiteScopeMiddleware:
    """
    Adds request-scoped info for:
      - site mode (dealership portal vs management portal)
      - current dealership for the user

    Management portal lives under /mgmt/.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = (request.path or "").lower()
        is_mgmt = path.startswith("/mgmt/")

        request.ns_site_mode = "management" if is_mgmt else "dealership"
        request.ns_site_namespace = "Management" if is_mgmt else "Dashboard"

        user = getattr(request, "user", None)
        can_view_all = user_can_view_all_dealerships(user) if user else False
        request.ns_can_view_all_dealerships = can_view_all
        request.ns_dealership = user_home_dealership(user)

        # Hard gate: only management/back office/staff can access /mgmt/
        if is_mgmt and user and user.is_authenticated and not can_view_all:
            return HttpResponseForbidden("You don't have permission to access the management site.")

        return self.get_response(request)

