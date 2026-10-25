from .models import Profile


def active(request):
    """Expose the profile list (for the navbar selector) everywhere."""
    return {
        "profiles": Profile.objects.filter(enabled=True).order_by("name"),
    }
