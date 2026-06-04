# @file
# @brief Command-line entry point for the handgrip realtime viewer.
##
# This module owns the @hydra.main decorator and is the only place where all
# subsystems are composed together. It deliberately contains no business
# logic: its sole responsibility is to read configuration, configure logging,
# and dispatch to the correct mode runner.
##
# Structured config registration must happen before @hydra.main is evaluated,
# which is why register_config() is called at import time.
##
# @note Runner imports were updated from runners.live / runners.replay to
# viz.app (NiceGUI-based runners), and matplotlib / PyQt5 are no longer
# imported anywhere in the package.
from __future__ import annotations

import logging
from pathlib import Path

import hydra
from omegaconf import DictConfig

from lsl_viewer.config import register_config
from lsl_viewer.logging_setup import configure_logging

log = logging.getLogger(__name__)

LIBRARY_ROOT = Path(__file__).parent.parent.parent.absolute()


# Mode strings supported by this viewer
_ALLOWED_MODES = frozenset({"live", "live_with_reference_validation", "csv_replay", "xdf_replay"})

# Register structured config schema before the decorator is processed
register_config()


@hydra.main(version_base=None, config_path=f"{LIBRARY_ROOT}/conf", config_name="config")
def app(cfg: DictConfig) -> int:
    # @brief Main Hydra entry point.
    # @param cfg Resolved Hydra configuration matching AppConfig.
    # @return Process exit code.
    # ── Logging ───────────────────────────────────────────────────────────
    # Called after Hydra init so we append handlers rather than replace them.
    configure_logging(
        cfg.logging.level,
        log_file=cfg.logging.log_file,
        max_bytes=cfg.logging.max_bytes,
        backup_count=cfg.logging.backup_count,
    )

    from omegaconf import OmegaConf

    log.info(
        "Starting dual-native-stream viewer with config:\n%s",
        OmegaConf.to_yaml(cfg, resolve=True),
    )

    # ── Mode validation ───────────────────────────────────────────────────
    mode = str(cfg.mode)
    if mode not in _ALLOWED_MODES:
        raise RuntimeError(f"Unsupported mode={mode!r}. Allowed modes: {sorted(_ALLOWED_MODES)}")

    # ── Mode dispatch ─────────────────────────────────────────────────────
    if mode == "live":
        from lsl_viewer.viz.app import run_live_mode_nicegui

        return run_live_mode_nicegui(cfg, validate_reference=False)

    if mode == "live_with_reference_validation":
        from lsl_viewer.viz.app import run_live_mode_nicegui

        return run_live_mode_nicegui(cfg, validate_reference=True)

    if mode == "csv_replay":
        from lsl_viewer.core.replay import load_csv_replay
        from lsl_viewer.viz.app import run_replay_mode_nicegui

        return run_replay_mode_nicegui(cfg, load_csv_replay(cfg), mode)

    if mode == "xdf_replay":
        from lsl_viewer.core.replay import load_xdf_replay
        from lsl_viewer.viz.app import run_replay_mode_nicegui

        return run_replay_mode_nicegui(cfg, load_xdf_replay(cfg), mode)

    raise AssertionError("Unreachable mode dispatch")  # pragma: no cover
