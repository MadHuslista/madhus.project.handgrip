"""Configuration loader and logging setup.

``load_app_config`` is the single entry point for configuration:
  1. Loads ``config/config.yaml`` relative to this file's package root.
  2. Merges OmegaConf dotlist overrides from CLI argv.
  3. Calls ``configure_logging`` once per process.

``@hydra.main`` is deliberately NOT used — this app is a simple CLI/script
entry point, so config is loaded directly via ``OmegaConf.load`` /
``OmegaConf.merge`` without a Hydra-managed run.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from omegaconf import DictConfig, OmegaConf

LOGGER = logging.getLogger(__name__)

# config/config.yaml is four levels above this file:
#   src/rs485_gui/config/loader.py  →  project_root/config/config.yaml
_CONFIG_PATH = Path(__file__).parent.parent.parent.parent / "config" / "config.yaml"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_app_config(argv: list[str] | None = None) -> DictConfig:
    """Load ``config/config.yaml`` and apply dotlist overrides from CLI argv.

    Args:
        argv: Override ``sys.argv[1:]`` for testing.

    Returns:
        Merged :class:`omegaconf.DictConfig`.

    The function handles ``-h`` / ``--help`` itself and raises
    :class:`SystemExit(0)` when the flag is present.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    cfg = OmegaConf.load(_CONFIG_PATH)

    overrides: list[str] = []
    ignored: list[str] = []

    for arg in args:
        if arg in {"-h", "--help"}:
            _print_help()
            raise SystemExit(0)
        # Silently skip Hydra-style flags for backward CLI compatibility
        if arg.startswith("hydra."):
            ignored.append(arg)
            continue
        if "=" in arg and not arg.startswith("--"):
            overrides.append(arg)
        else:
            ignored.append(arg)

    if overrides:
        cfg = OmegaConf.merge(cfg, OmegaConf.from_dotlist(overrides))

    configure_logging(cfg)

    if ignored:
        LOGGER.warning("Ignoring unsupported CLI args: %s", ignored)

    return cfg


# @brief Configure logging.
#
#  @param cfg Parameter description.
def configure_logging(cfg: DictConfig) -> None:
    """Set up the root logger with a stream handler and optional file handler."""
    root = logging.getLogger()

    # Prefer logging.root_level (new) over app.log_level (legacy alias)
    level_str = str(
        getattr(getattr(cfg, "logging", None), "root_level", None) or cfg.app.log_level
    ).upper()
    level = getattr(logging, level_str, logging.INFO)
    root.setLevel(level)

    formatter = logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")

    # Console handler
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(level)
    stream_handler.setFormatter(formatter)
    root.addHandler(stream_handler)

    # Optional file handler (mirrors console output to logs/acquisition_debug.log)
    if cfg.logger.debug_log_to_file:
        log_dir = Path(str(cfg.logger.directory)).expanduser()
        log_dir.mkdir(parents=True, exist_ok=True)
        file_mode = "a" if str(cfg.logger.write_mode).lower() == "append" else "w"
        file_handler = logging.FileHandler(
            log_dir / str(cfg.logger.debug_log_filename),
            mode=file_mode,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    # Apply per-module level overrides (new in v0.2)
    try:
        module_levels = (
            OmegaConf.to_container(
                getattr(
                    getattr(cfg, "logging", OmegaConf.create({})),
                    "module_levels",
                    OmegaConf.create({}),
                ),
                resolve=True,
            )
            or {}
        )
        for module_name, level_str in module_levels.items():
            lvl = getattr(logging, str(level_str).upper(), logging.INFO)
            logging.getLogger(module_name).setLevel(lvl)
    except Exception:
        pass  # module_levels section is optional


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _print_help() -> None:
    print(
        "Usage: python -m rs485_gui [key=value ...]\n\n"
        "Examples:\n"
        "  python -m rs485_gui\n"
        "  python -m rs485_gui ui.port=8090 serial.default_port=/dev/ttyUSB0\n"
        "  python -m rs485_gui device.mode=active_send\n"
        "  python -m rs485_gui app.log_level=DEBUG\n\n"
        "All keys from config/config.yaml are available as dotlist overrides.\n"
        "Configuration precedence (highest wins):\n"
        "  CLI overrides > config/config.yaml defaults\n"
    )
