"""Typed exception hierarchy for the handgrip realtime viewer.

All viewer exceptions inherit from ViewerError so callers can handle
them with a single broad clause when needed, while still being able
to distinguish between user-configuration errors, stream failures,
and replay-loading failures.
"""
from __future__ import annotations


class ViewerError(Exception):
    """Base class for all viewer errors."""

    exit_code: int = 1

    def user_message(self) -> str:
        """Human-readable description suitable for display."""
        return str(self)

    def remediation(self) -> str | None:
        """Suggested corrective action, if known."""
        return None


class ConfigurationError(ViewerError):
    """Invalid or inconsistent configuration supplied by the user."""

    exit_code = 2

    def __init__(self, message: str, fix: str | None = None) -> None:
        super().__init__(message)
        self._fix = fix

    def remediation(self) -> str | None:
        return self._fix


class StreamConnectionError(ViewerError):
    """Failed to connect to or read from an LSL stream."""

    exit_code = 3

    def __init__(self, stream_name: str, reason: str) -> None:
        super().__init__(f"Stream '{stream_name}': {reason}")
        self.stream_name = stream_name
        self.reason = reason

    def remediation(self) -> str | None:
        return (
            f"Ensure an LSL stream named '{self.stream_name}' is active "
            "on the network before starting the viewer."
        )


class ReplayLoadError(ViewerError):
    """Failed to load a CSV or XDF replay dataset."""

    exit_code = 4

    def __init__(self, path: str, reason: str) -> None:
        super().__init__(f"Cannot load replay file '{path}': {reason}")
        self.path = path
        self.reason = reason
