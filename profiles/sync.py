import logging

from django.utils import translation

from core import config

from .models import Profile, ProfileSyncResult

logger = logging.getLogger(__name__)


def sync_profile(cfg):
    """Persist a validated ProfileConfig into the Profile table."""
    return Profile.from_config(cfg)


def sync_all(raise_on_error=False):
    """Load every `profiles/*.yaml`, validate and sync each.

    Returns a list of (name, success, [error messages]) tuples.
    """
    results = []
    for name in config.available_profile_names():
        try:
            cfg = config.load_profile(name)
        except config.ConfigError as exc:
            with translation.override("en"):
                errors = [str(exc)] + [str(e) for e in exc.errors]
            logger.error("Profile %s invalid: %s", name, errors)
            results.append((name, False, errors))
            ProfileSyncResult.objects.create(
                name=name, success=False, errors=str(errors)
            )
            if raise_on_error:
                raise
            continue
        sync_profile(cfg)
        ProfileSyncResult.objects.create(name=name, success=True, errors="[]")
        results.append((name, True, []))
    return results
