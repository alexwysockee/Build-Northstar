from django.shortcuts import redirect
from django.conf import settings


class RequireLoginMiddleware:
    """Redirect unauthenticated users to login for all pages except login, logout, admin, and static."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            path = request.path
            if path.startswith("/static/") or path.startswith("/static"):
                return self.get_response(request)
            # Allow home (login) and logout pages
            if path.rstrip("/") in (settings.LOGIN_URL.rstrip("/"), "/logout"):
                return self.get_response(request)
            # Allow admin
            if path.startswith("/admin/"):
                return self.get_response(request)
            return redirect(settings.LOGIN_URL + "?next=" + request.get_full_path())
        return self.get_response(request)
