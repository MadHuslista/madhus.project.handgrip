# @package handgrip_analysis.config.schema
# @brief Root application configuration schema and Hydra registration hooks.

"""
Root application configuration schema.

Provides the ``AppConfig`` dataclass that aggregates all sub-configs and
optionally registers them with Hydra's ``ConfigStore`` so that structured
config validation fires at Hydra initialisation time.

Usage
-----
Call ``register_configs()`` once at application startup (before ``@hydra.main``
or ``hydra.initialize()``) to wire in the structured config defaults::

    from handgrip_analysis.config.schema import register_configs
    register_configs()

For non-Hydra usage (tests, library code), construct directly::

    from handgrip_analysis.config import AppConfig
    cfg = AppConfig()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .dsp_config import DSPConfig

# ---------------------------------------------------------------------------
# Logging config
# ---------------------------------------------------------------------------


@dataclass
# @brief Logging configuration.
# @param level Root logger level string.
# @param file Optional path for file logging output.
class LoggingConfig:
    """
    Logging configuration.

    Attributes
    ----------
    level:
        Root logger level string: ``"DEBUG"``, ``"INFO"``, ``"WARNING"``,
        ``"ERROR"``, or ``"CRITICAL"`` (case-insensitive).
    file:
        Optional path for the log file.  ``None`` disables file logging.

    """

    level: str = "INFO"
    file: str | None = None

    # @brief Validate configured logging level.
    # @param self Instance pointer.
    # @return None.
    def __post_init__(self) -> None:
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if self.level.upper() not in valid:
            raise ValueError(f"LoggingConfig.level must be one of {valid}, got {self.level!r}")

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None = None) -> "LoggingConfig":
        data = dict(data or {})
        kwargs: dict[str, Any] = {}
        if "level" in data:
            kwargs["level"] = str(data["level"])
        if "file" in data:
            kwargs["file"] = data["file"]
        return cls(**kwargs)


# ---------------------------------------------------------------------------
# Stage 6 scoring weights
# ---------------------------------------------------------------------------


@dataclass
# @brief Composite score weights for Stage 6 filter-family review.
# @param review_weight Weight for review ranking component.
# @param design_weight Weight for design assessment component.
class Stage6ScoringConfig:
    """
    Composite score weights for the Stage 6 filter family review.

    The two components are:

    * *review_weight* — weight applied to the per-trial metric-based ranking
      (``build_stage6_design_assessment``).
    * *design_weight* — weight applied to the filter design quality assessment
      (``_design_weighted_score``).

    The two weights must sum to 1.0.
    """

    review_weight: float = 0.7
    design_weight: float = 0.3

    # @brief Validate Stage 6 scoring weights sum to one.
    # @param self Instance pointer.
    # @return None.
    def __post_init__(self) -> None:
        total = self.review_weight + self.design_weight
        if abs(total - 1.0) > 1e-9:
            raise ValueError(f"Stage6ScoringConfig weights must sum to 1.0, got {total:.6f}")

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None = None) -> "Stage6ScoringConfig":
        data = dict(data or {})
        kwargs: dict[str, Any] = {}
        if "review_weight" in data:
            kwargs["review_weight"] = float(data["review_weight"])
        if "design_weight" in data:
            kwargs["design_weight"] = float(data["design_weight"])
        return cls(**kwargs)


# ---------------------------------------------------------------------------
# Root application config
# ---------------------------------------------------------------------------


@dataclass
# @brief Root application configuration aggregating all sub-configs.
# @param dsp DSP algorithm configuration.
# @param logging Logging configuration.
# @param stage6_scoring Stage 6 composite scoring configuration.
class AppConfig:
    """
    Root application configuration aggregating all sub-configs.

    This class provides a single, validated configuration object that can be
    constructed from Hydra's composed config or directly in tests.
    """

    dsp: DSPConfig = field(default_factory=DSPConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    stage6_scoring: Stage6ScoringConfig = field(default_factory=Stage6ScoringConfig)

    # @brief Build an AppConfig from a nested mapping.
    # @param cls Class type.
    # @param data Nested mapping (for example Hydra DictConfig).
    # @return A validated AppConfig instance.
    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None = None) -> "AppConfig":
        """Build an ``AppConfig`` from a nested mapping (e.g. Hydra DictConfig)."""
        data = dict(data or {})
        dsp = DSPConfig.from_mapping(data.get("dsp"))
        logging_cfg = LoggingConfig.from_mapping(data.get("logging"))
        stage6 = Stage6ScoringConfig.from_mapping(data.get("stage6_scoring"))
        return cls(dsp=dsp, logging=logging_cfg, stage6_scoring=stage6)


# ---------------------------------------------------------------------------
# Hydra ConfigStore registration (optional — only when hydra-core is in use)
# ---------------------------------------------------------------------------


# @brief Register AppConfig with Hydra ConfigStore when Hydra is available.
# @return None.
def register_configs() -> None:
    """
    Register ``AppConfig`` with Hydra's ``ConfigStore``.

    Call this once at application startup, before any ``hydra.initialize()``
    or ``@hydra.main`` decorated entry point runs.  Safe to call multiple
    times — subsequent calls are no-ops.
    """
    try:
        from hydra.core.config_store import ConfigStore
    except ImportError:  # pragma: no cover
        return

    cs = ConfigStore.instance()
    cs.store(name="app_config", node=AppConfig)
