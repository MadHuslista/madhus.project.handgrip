"""Processing module loader for the LSL Bridge.

Loads the signal-processing module named by ``processing.module`` in config
via ``importlib`` so that alternative processor implementations can be
substituted without changing source code — only the config needs updating.

The loaded module must expose a ``build_processor(cfg)`` callable that
returns an object implementing the ``Processor`` protocol (i.e. it must
have a ``process(value: float, sample_time_s: float) -> float`` method).
"""

from __future__ import annotations

import importlib
import logging

from omegaconf import DictConfig

from lsl_bridge.types import Processor

_log = logging.getLogger(__name__)


def build_processor(cfg: DictConfig) -> Processor:
    """Load and instantiate the configured processor.

    Args:
        cfg: Full Hydra ``DictConfig``.  Uses ``processing.module``.

    Returns:
        An object satisfying the ``Processor`` protocol.

    Raises:
        TypeError: If the loaded module's factory returns an object that
                   does not implement ``process()``.
    """
    module_name = str(cfg.processing.module)
    _log.debug("Loading processing module: %s", module_name)
    module = importlib.import_module(module_name)
    processor = module.build_processor(cfg.processing)
    if not hasattr(processor, "process"):
        raise TypeError(
            f"processing module {module_name!r} returned an object "
            "without a process() method"
        )
    _log.debug("Processor loaded: %s", type(processor).__name__)
    return processor
