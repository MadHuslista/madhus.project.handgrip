# @package lsl_bridge.logging_setup
#  @brief Logging bootstrap utilities for LSL Bridge runtime.
##
"""
Logging configuration for the LSL Bridge.

``configure_logging`` wires the root logger with a console handler and,
optionally, a rotating file handler.  Both handlers share the same level
and format, which are read from the Hydra config so they can be changed
without touching source code.

Typical usage (inside the Hydra ``app`` entry point)::

    from lsl_bridge.logging_setup import configure_logging
    configure_logging(cfg)

Override from the command line::

    python -m lsl_bridge logging.level=DEBUG
    python -m lsl_bridge logging=debug     # switches to the debug config group
"""

from __future__ import annotations

import logging
import subprocess as sp
import sys
from pathlib import Path

from omegaconf import DictConfig

_log = logging.getLogger(__name__)

REPO_ROOT = Path(sp.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()).absolute() / "LSL_Bridge"


# @brief Configure root logging handlers from Hydra configuration.
#  @param cfg Full Hydra configuration containing logging settings.
#  @return None.
def configure_logging(cfg: DictConfig) -> None:
    """
    Attach console and optional file handlers to the root logger.

    Both handlers receive the same ``level`` and ``format`` defined in
    ``cfg.logging``.  If ``cfg.logging.file`` is ``null`` / ``None``,
    only the console handler is installed.

    This function is idempotent with respect to the root logger: it clears
    any handlers installed by Hydra's own logging initialisation before
    attaching the bridge's handlers, preventing duplicate log lines.

    Args:
        cfg: Full Hydra ``DictConfig`` object.  Uses the ``logging``
             sub-tree (``level``, ``file``, ``format``).

    """
    level_name = str(cfg.logging.level).upper()
    level = getattr(logging, level_name, logging.INFO)
    fmt = str(cfg.logging.format)
    formatter = logging.Formatter(fmt)

    root = logging.getLogger()
    # Remove handlers Hydra may have installed to avoid duplicate lines.
    root.handlers.clear()
    root.setLevel(level)

    # Console handler — always present.
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    console.setLevel(level)
    root.addHandler(console)

    # File handler — optional; disabled when cfg.logging.file is null.
    log_file = cfg.logging.get("file")
    if log_file:
        file_path = Path(str(log_file))
        file_path.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(file_path, encoding="utf-8")
        fh.setFormatter(formatter)
        fh.setLevel(level)
        root.addHandler(fh)
        _log.debug("File logging enabled: %s", file_path.resolve())
