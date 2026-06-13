from accounts.models import Borlette

from django.db.utils import OperationalError, ProgrammingError


def portal_context(request):
    borlette = None

    user = getattr(request, "user", None)
    if user and getattr(user, "is_authenticated", False):
        try:
            borlette = user.borlette
        except Borlette.DoesNotExist:
            borlette = None
        except (OperationalError, ProgrammingError):
            borlette = None

    return {
        "portal_borlette": borlette,
    }
