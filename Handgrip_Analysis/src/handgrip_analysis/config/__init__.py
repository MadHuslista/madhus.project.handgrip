# @package handgrip_analysis.config
# @brief Structured configuration dataclasses for handgrip-analysis.

"""
Structured configuration dataclasses for handgrip-analysis.

These dataclasses are the authoritative typed definitions for all algorithm
constants and tunable parameters.  The YAML files under ``conf/`` are the
override surface; the defaults here must match ``conf/dsp/defaults.yaml``.

Usage
-----
Import the top-level ``AppConfig`` for Hydra-registered structured configs,
or instantiate the individual sub-configs directly in tests and library code::

    from handgrip_analysis.config import DSPConfig, PlotConfig

"""
from .dsp_config import DSPConfig, EventDetectionConfig, PlotConfig, PsdPeaksConfig, WelchConfig
from .schema import AppConfig, LoggingConfig, register_configs

__all__ = [
    "AppConfig",
    "DSPConfig",
    "EventDetectionConfig",
    "LoggingConfig",
    "PlotConfig",
    "PsdPeaksConfig",
    "WelchConfig",
    "register_configs",
]
