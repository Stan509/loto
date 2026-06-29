def portal_context(request):
    borlette = None

    user = getattr(request, "user", None)
    if user and getattr(user, "is_authenticated", False):
        try:
            borlette = user.borlette
        except Exception:
            # Catches: RelatedObjectDoesNotExist, Borlette.DoesNotExist,
            #          OperationalError, ProgrammingError, AttributeError, etc.
            borlette = None

    return {
        "portal_borlette": borlette,
    }
