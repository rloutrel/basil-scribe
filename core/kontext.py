"""
Context sources — anticipated extension, disabled in v1.

`ContextSource` is the seam for a future historical-context block
(e.g. a semantic search index over the archive). The default
implementation, `NullContext`, returns an empty list, and generation
must never be blocked by context being disabled or failing.
"""

import logging

logger = logging.getLogger(__name__)


class ContextSource:
    """Interface for context providers. Extend in a later version."""

    def get_context(self, request_text, profile, request_type, limit=3):
        """Return a list of context strings for the given request."""
        raise NotImplementedError


class NullContext(ContextSource):
    """Default no-op context source used while the extension is off."""

    def get_context(self, request_text, profile, request_type, limit=3):
        return []


def get_context_source(profile):
    """Resolve the context source for a profile.

    Never raises: unknown or disabled context always falls back to
    NullContext so generation is never blocked.
    """
    if profile is not None and getattr(profile, "context_enabled", False):
        logger.info(
            "Context enabled for profile %s but no adapter exists yet; "
            "falling back to NullContext",
            getattr(profile, "name", "?"),
        )
    return NullContext()
