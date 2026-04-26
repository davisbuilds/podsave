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


class DurationGuardError(PodsaveError):
    pass


class DownloadError(PodsaveError):
    pass


class TranscriptionError(PodsaveError):
    pass


class EmptyExtractionError(PodsaveError):
    """Raised by the CLI when extraction returns zero items.

    The model is allowed to return zero items (especially under a tight `--focus`).
    The CLI surfaces it as a clean exit-1 with an actionable message rather than
    writing an empty-body note to the vault.
    """
