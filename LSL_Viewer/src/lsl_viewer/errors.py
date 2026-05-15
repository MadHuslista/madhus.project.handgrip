# @file
# @brief Typed exception hierarchy for the handgrip realtime viewer.
##
# All viewer exceptions inherit from ViewerError so callers can handle them
# with a single broad clause when needed, while still being able to distinguish
# between user-configuration errors, stream failures, and replay-loading failures.
from __future__ import annotations


class ViewerError(Exception):
    # @brief Base class for all viewer errors.

    exit_code: int = 1

    def user_message(self) -> str:
        # @brief Human-readable description suitable for display.
        # @return Displayable error message.
        return str(self)

    def remediation(self) -> str | None:
        # @brief Suggested corrective action, if known.
        # @return Remediation text or None.
        return None


class ConfigurationError(ViewerError):
    # @brief Invalid or inconsistent configuration supplied by the user.

    exit_code = 2

    def __init__(self, message: str, fix: str | None = None) -> None:
        # @brief Create a configuration error.
        # @param message Error message.
        # @param fix Optional remediation text.
        super().__init__(message)
        self._fix = fix

    def remediation(self) -> str | None:
        # @brief Suggested corrective action, if known.
        # @return Remediation text or None.
        return self._fix


class StreamConnectionError(ViewerError):
    # @brief Failed to connect to or read from an LSL stream.

    exit_code = 3

    def __init__(self, stream_name: str, reason: str) -> None:
        # @brief Create a stream-connection error.
        # @param stream_name Name of the stream that failed.
        # @param reason Failure reason.
        super().__init__(f"Stream '{stream_name}': {reason}")
        self.stream_name = stream_name
        self.reason = reason

    def remediation(self) -> str | None:
        # @brief Suggested corrective action, if known.
        # @return Remediation text.
        return (
            f"Ensure an LSL stream named '{self.stream_name}' is active "
            "on the network before starting the viewer."
        )


class ReplayLoadError(ViewerError):
    # @brief Failed to load a CSV or XDF replay dataset.

    exit_code = 4

    def __init__(self, path: str, reason: str) -> None:
        # @brief Create a replay-load error.
        # @param path Replay file path.
        # @param reason Failure reason.
        super().__init__(f"Cannot load replay file '{path}': {reason}")
        self.path = path
        self.reason = reason
