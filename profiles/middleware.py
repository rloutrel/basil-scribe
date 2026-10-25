import logging

from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import translation
from django.utils.translation import gettext as _

from .models import Profile

logger = logging.getLogger(__name__)

SESSION_KEY = "active_profile"


def get_active_profile(request):
    """Return the session's active profile, or the first available."""
    name = request.session.get(SESSION_KEY)
    if name:
        profile = Profile.objects.filter(name=name, enabled=True).first()
        if profile:
            return profile
    return Profile.objects.filter(enabled=True).order_by("name").first()


def set_active_profile(request, name):
    profile = get_object_or_404(Profile, name=name, enabled=True)
    request.session[SESSION_KEY] = profile.name
    return profile


class ActiveProfileMiddleware:
    """Resolve the active profile and switch the UI language to it."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        profile = None
        try:
            profile = get_active_profile(request)
        except Http404:
            pass
        except Exception:
            logger.exception("Could not resolve the active profile")
        request.active_profile = profile
        if profile:
            translation.activate(profile.language)
            request.LANGUAGE_CODE = translation.get_language()
        response = self.get_response(request)
        if profile:
            response.setdefault("Content-Language", translation.get_language())
            translation.deactivate()
        return response


def activate_profile_language(profile):
    """Activate the working language of a profile (for commands)."""
    if profile and getattr(profile, "language", None):
        translation.activate(profile.language)
