"""Logging configuration for handgrip_calibration.

Sets up a hierarchical logging system rooted at the ``handgrip_calibration``
logger with two handlers:

* **Console handler** — writes to ``stderr`` at the configured level.
* **File handler** — writes to ``<session_dir>/session.log`` always at
  ``DEBUG`` so the full trace is available for post-hoc investigation even
  when the console is set to ``INFO``.

Usage::

    from handgrip_calibration.logging_setup import configure_logging
    configure_logging(level="INFO", log_file=paths.session_log)

All module-level loggers should be created with::

    import logging
    log = logging.getLogger(__name__)

This automatically places them under the ``handgrip_calibration`` namespace
and inherits the handlers set up here.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_LOG_FORMAT = "%(asctime)s [%(levelname)-8s] %(name)s — %(message)s"
_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"

_ROOT_LOGGER_NAME = "handgrip_calibration"


def configure_logging(
    *,
    level: str = "INFO",
    log_file: Path | None = None,
) -> None:
    """Configure the package-root logger.

    Parameters
    ----------
    level:
        Console verbosity.  One of ``DEBUG``, ``INFO``, ``WARNING``,
        ``ERROR``, ``CRITICAL``.  Case-insensitive.
    log_file:
        Optional path for the file log.  The parent directory is created
        automatically.  The file handler always runs at ``DEBUG`` level so
        no detail is lost regardless of the console setting.
    """
    root = logging.getLogger(_ROOT_LOGGER_NAME)
    root.setLevel(logging.DEBUG)  # Root always at DEBUG; handlers filter
    root.handlers.clear()

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    # ── Console handler ───────────────────────────────────────────────
    console = logging.StreamHandler(sys.stderr)
    console_level = getattr(logging, level.upper(), logging.INFO)
    console.setLevel(console_level)
    console.setFormatter(formatter)
    root.addHandler(console)

    # ── File handler ─────────────────────────────────────────────────
    if log_file is not None:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(formatter)
        root.addHandler(fh)
