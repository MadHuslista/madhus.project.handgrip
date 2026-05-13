"""
Centralised logging setup for the handgrip-analysis package.

Usage
-----
Call ``setup_logging()`` **once** at the application entry point (main script
or Hydra post-initialisation).  Library modules must *not* call this function;
they obtain their logger via::

    import logging
    log = logging.getLogger(__name__)
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path


def setup_logging(
    level: str = "INFO",
    log_file: str | Path | None = None,
) -> None:
    """
    Configure the root logger with a console handler and an optional file handler.

    Both handlers share the same formatter so that every console message is also
    captured in the log file.

    Parameters
    ----------
    level:
        Logging level string: ``"DEBUG"``, ``"INFO"``, ``"WARNING"``,
        ``"ERROR"``, or ``"CRITICAL"`` (case-insensitive).
    log_file:
        If provided, log output is also written to this path.  Parent
        directories are created automatically.
    """
    root = logging.getLogger()
    root.setLevel(level.upper())

    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    # Console handler — stdout so it can be captured/redirected
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    root.addHandler(ch)

    # File handler — mirrors console output
    if log_file is not None:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_path, encoding="utf-8")
        fh.setFormatter(fmt)
        root.addHandler(fh)
        # Emit via the module logger now that the file handler is installed.
        logging.getLogger(__name__).info("Logging to file: %s", log_path)
