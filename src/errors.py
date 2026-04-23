from __future__ import annotations


class PodsaveError(Exception):
    """Base class for actionable user-facing errors.

    Messages should name the file or command needed to fix the problem.
    """


class ConfigMissingError(PodsaveError):
    pass


class ConfigInvalidError(PodsaveError):
    pass


class TranscriptNotFoundError(PodsaveError):
    pass


class InvalidYouTubeURLError(PodsaveError):
    pass


class PlaylistURLError(PodsaveError):
    pass


class ProbeError(PodsaveError):
    pass
