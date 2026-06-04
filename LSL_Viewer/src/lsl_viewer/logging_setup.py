# @file
# @brief Logging configuration for the handgrip realtime viewer.
##
# Design principles:
# - Called inside the @hydra.main body so Hydra has already set up its own handlers.
# - force=True is intentionally absent because it tears out existing handlers.
# - A RotatingFileHandler keeps logs bounded across long runs.
# - Module-scoped loggers inherit this root configuration automatically.
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
    # @brief Configure root logger with a console handler and a rotating file handler.
    # @param level_name Case-insensitive log level string.
    # @param log_file Path for the rotating log file.
    # @param max_bytes Maximum size of a single log file before rotation.
    # @param backup_count Number of rotated backup files to retain.
    level = getattr(logging, level_name.upper(), logging.INFO)
    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    root = logging.getLogger()
    root.setLevel(level)

    # ── Console handler ───────────────────────────────────────────────────
    # Add only if no StreamHandler is already present (avoids duplicates when
    # called more than once, e.g. during test runs).
    if not any(isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler) for h in root.handlers):
        console = logging.StreamHandler()
        console.setLevel(level)
        console.setFormatter(formatter)
        root.addHandler(console)

    # ── Rotating file handler ─────────────────────────────────────────────
    resolved = str(Path(log_file).resolve())
    if not any(
        isinstance(h, logging.handlers.RotatingFileHandler) and getattr(h, "baseFilename", None) == resolved
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
