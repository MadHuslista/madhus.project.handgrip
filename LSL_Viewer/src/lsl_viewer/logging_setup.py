"""Logging configuration for the handgrip realtime viewer.

Design principles
-----------------
* Called *inside* the ``@hydra.main`` body so Hydra has already set up its
  own handlers.  We append to the root logger rather than replacing it, which
  means Hydra's own file handler (if any) is preserved.
* ``force=True`` is intentionally absent: that flag tears out existing handlers
  and was the reason the repository's ``.log`` file was always empty.
* A ``RotatingFileHandler`` is installed so log output survives long runs and
  multiple restarts without filling disk.
* Module-scoped loggers (``logging.getLogger(__name__)``) throughout the package
  inherit this root configuration automatically.
"""
from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def configure_logging(
    level_name: str,
    log_file: str | Path,
    max_bytes: int = 10_485_760,
    backup_count: int = 3,
) -> None:
    """Configure root logger with a console handler and a rotating file handler.

    Parameters
    ----------
    level_name:
        Case-insensitive log level string (e.g. ``"INFO"``, ``"DEBUG"``).
    log_file:
        Path for the rotating log file.  Parent directories must exist or the
        file must be writable in the current directory.
    max_bytes:
        Maximum size of a single log file before rotation.  Defaults to 10 MB.
    backup_count:
        Number of rotated backup files to retain.
    """
    level = getattr(logging, level_name.upper(), logging.INFO)
    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    root = logging.getLogger()
    root.setLevel(level)

    # ── Console handler ───────────────────────────────────────────────────
    # Add only if no StreamHandler is already present (avoids duplicates when
    # called more than once, e.g. during test runs).
    if not any(
        isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
        for h in root.handlers
    ):
        console = logging.StreamHandler()
        console.setLevel(level)
        console.setFormatter(formatter)
        root.addHandler(console)

    # ── Rotating file handler ─────────────────────────────────────────────
    resolved = str(Path(log_file).resolve())
    if not any(
        isinstance(h, logging.handlers.RotatingFileHandler)
        and getattr(h, "baseFilename", None) == resolved
        for h in root.handlers
    ):
        fh = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        fh.setLevel(level)
        fh.setFormatter(formatter)
        root.addHandler(fh)
