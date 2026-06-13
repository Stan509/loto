"""
Middleware pour forcer le changement de mot de passe après connexion avec un mot de passe temporaire.
"""
from django.shortcuts import redirect


class ForcePasswordChangeMiddleware:
    """Redirige vers la page de changement de mot de passe si must_change_password est True."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and request.user.must_change_password:
            allowed_paths = {
                "/account/force-password-change/",
                "/logout/",
                "/static/",
                "/media/",
            }
            path = request.path
            if not any(path.startswith(a) for a in allowed_paths):
                return redirect("force_password_change")

        response = self.get_response(request)
        return response
