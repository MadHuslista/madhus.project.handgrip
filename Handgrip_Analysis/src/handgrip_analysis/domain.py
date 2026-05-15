# @package handgrip_analysis.domain
# @brief Domain models for trial-aware handgrip analysis.

"""
Domain models for trial-aware handgrip analysis.

This module defines the small, immutable data contracts used by the Phase 1
multi-trial refactor.  The intent is to make the statistical unit explicit:
analysis operates on *trials*, and trial results are later aggregated into
conditions/stages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

MetricValue = int | float | str | bool | None
Metrics = dict[str, MetricValue]


@dataclass(frozen=True, slots=True)
# @brief Validated manifest row describing one capture trial.
# @param stage Logical stage name.
# @param condition Condition label for aggregation.
# @param trial_type Semantic trial type inside a stage.
# @param trial_id Human-readable trial identifier.
# @param session_id Acquisition session identifier.
# @param path Capture CSV path.
# @param channel Analyzer signal channel.
# @param include Include flag for analysis selection.
# @param load_nominal_n Optional known nominal load.
# @param notes Free-form operator notes.
class TrialSpec:
    """
    Validated manifest row describing one capture trial.

    Parameters
    ----------
    stage:
        Logical stage name, for example ``"stage1"`` or ``"stage4"``.
    condition:
        Condition being replicated, for example ``"cold_start"`` or
        ``"fast_max"``.  Aggregation is performed at this level.
    trial_type:
        Semantic type of trial within a stage.  For stage 4 this commonly
        distinguishes ``fast_max``, ``ramp_hold``, and ``sustained_hold``.
    trial_id:
        Human-readable trial identifier unique within ``session_id`` and
        condition.
    session_id:
        Acquisition session/date/run identifier.  Kept explicit so later
        validation can split by session without leaking trials.
    path:
        Capture CSV path.  It is normalized to an absolute path by the manifest
        loader.
    channel:
        Signal channel consumed by the analyzer.  The current capture loader
        supports ``raw`` and ``filtered``.
    include:
        False rows are kept in the manifest table but excluded from analysis.
    load_nominal_n:
        Optional known load for static loaded trials.
    notes:
        Free-form operator notes.

    """

    stage: str
    condition: str
    trial_type: str
    trial_id: str
    session_id: str
    path: Path
    channel: str = "raw"
    include: bool = True
    load_nominal_n: float | None = None
    notes: str = ""

    @property
    # @brief Return a stable compact identifier for filenames and tables.
    # @param self Instance pointer.
    # @return Compact trial identity string.
    def identity(self) -> str:
        """Stable compact identifier used in filenames and tables."""
        return f"{self.stage}__{self.condition}__{self.session_id}__{self.trial_id}"

    def to_record(self) -> dict[str, Any]:
        # @brief Return a JSON/CSV-friendly representation of this trial.
        # @param self Instance pointer.
        # @return Dictionary representation.
        """Return a JSON/CSV friendly representation."""
        return {
            "stage": self.stage,
            "condition": self.condition,
            "trial_type": self.trial_type,
            "trial_id": self.trial_id,
            "session_id": self.session_id,
            "path": str(self.path),
            "channel": self.channel,
            "include": self.include,
            "load_nominal_n": self.load_nominal_n,
            "notes": self.notes,
        }


@dataclass(frozen=True, slots=True)
# @brief Typed configuration consumed by stage analyzers.
# @param stage Stage key.
# @param time_source Time-source selection policy.
# @param channel Default analysis channel.
# @param channels Multi-channel analysis tuple.
# @param warmup_window_s Warmup rolling window in seconds.
# @param pre_window_s Pre-window duration in seconds.
# @param post_window_s Post-window duration in seconds.
# @param baseline_s Event baseline duration in seconds.
# @param threshold_sigma Event threshold in sigma units.
# @param min_duration_s Minimum event duration in seconds.
# @param merge_gap_s Event merge gap in seconds.
# @param pad_s Event padding in seconds.
# @param bandpower_bands Bandpower frequency bands.
# @param filter_config Optional candidate filter config path.
# @param lsl_bridge_root Optional LSL bridge root path.
# @param lsl_bridge_config Optional LSL bridge config path.
# @param stage_context_manifest Optional Stage 1-5 context manifest path.
# @param hf_noise_band_hz High-frequency noise band.
# @param filter_weights Composite scoring weights.
# @param min_trials_allowed Minimum allowed trials.
# @param min_trials_recommended Minimum recommended trials.
# @param confidence_level Confidence interval level.
# @param bootstrap_resamples Number of bootstrap resamples.
# @param random_seed Random seed.
class StageConfig:
    """
    Typed configuration used by stage analyzers.

    The class intentionally contains the common knobs needed by all stages plus
    stage-specific fields that are harmless when unused.  Construction happens
    at the boundary, keeping stage functions simple and deterministic for a
    given ``TrialSpec`` and configuration.
    """

    stage: str
    time_source: str = "auto"
    channel: str = "raw"
    channels: tuple[str, ...] = ("raw",)
    warmup_window_s: float = 10.0
    pre_window_s: float = 10.0
    post_window_s: float = 10.0
    baseline_s: float = 2.0
    threshold_sigma: float = 5.0
    min_duration_s: float = 0.20
    merge_gap_s: float = 0.15
    pad_s: float = 0.25
    bandpower_bands: tuple[tuple[float, float], ...] = (
        (0.0, 1.0),
        (1.0, 4.0),
        (4.0, 12.0),
        (12.0, 30.0),
        (30.0, 49.0),
    )
    filter_config: Path | None = None
    lsl_bridge_root: Path | None = None
    lsl_bridge_config: Path | None = None
    stage_context_manifest: Path | None = None
    hf_noise_band_hz: tuple[float, float] = (30.0, 49.0)
    filter_weights: Mapping[str, float] = field(
        default_factory=lambda: {
            "rest_std_norm": 0.25,
            "mean_peak_relative_error": 0.35,
            "mean_rise_relative_error": 0.10,
            "mean_peak_time_shift_norm": 0.10,
            "mean_dfdt_deviation": 0.20,
        }
    )
    min_trials_allowed: int = 1
    min_trials_recommended: int = 5
    confidence_level: float = 0.95
    bootstrap_resamples: int = 5000
    random_seed: int = 42

    # @brief Build a StageConfig from a loose mapping.
    # @param cls Class type.
    # @param stage Stage key.
    # @param data Mapping payload, such as Hydra/OmegaConf container.
    # @return StageConfig instance.
    @classmethod
    def from_mapping(cls, stage: str, data: Mapping[str, Any] | None = None) -> "StageConfig":
        """Build a config from a loose mapping such as a Hydra/OmegaConf dict."""
        data = dict(data or {})
        if "bandpower_bands" in data:
            data["bandpower_bands"] = tuple(tuple(map(float, b)) for b in data["bandpower_bands"])
        if "channels" in data:
            data["channels"] = tuple(str(ch) for ch in data["channels"])
        if "filter_config" in data and data["filter_config"] is not None:
            data["filter_config"] = Path(data["filter_config"])
        if "lsl_bridge_root" in data and data["lsl_bridge_root"] is not None:
            data["lsl_bridge_root"] = Path(data["lsl_bridge_root"])
        if "lsl_bridge_config" in data and data["lsl_bridge_config"] is not None:
            data["lsl_bridge_config"] = Path(data["lsl_bridge_config"])
        if "stage_context_manifest" in data and data["stage_context_manifest"] is not None:
            data["stage_context_manifest"] = Path(data["stage_context_manifest"])
        if "hf_noise_band_hz" in data:
            lo, hi = data["hf_noise_band_hz"]
            data["hf_noise_band_hz"] = (float(lo), float(hi))
        allowed = set(cls.__dataclass_fields__) - {"stage"}
        filtered = {k: v for k, v in data.items() if k in allowed}
        return cls(stage=stage, **filtered)


@dataclass(frozen=True, slots=True)
# @brief Result produced by one stage analyzer for one trial.
# @param spec Source trial specification.
# @param metrics Scalar metrics dictionary.
# @param tables Optional named tabular artifacts.
# @param artifacts Optional named file artifacts.
class TrialResult:
    """Result produced by one stage analyzer for one trial."""

    spec: TrialSpec
    metrics: Metrics
    tables: Mapping[str, pd.DataFrame] = field(default_factory=dict, repr=False, compare=False)
    artifacts: Mapping[str, Path] = field(default_factory=dict)

    # @brief Flatten trial identity and scalar metrics into one row.
    # @param self Instance pointer.
    # @return Flattened dictionary row.
    def metrics_record(self) -> dict[str, Any]:
        """Flatten trial identity and scalar metrics into one table row."""
        return {**self.spec.to_record(), **self.metrics}


@dataclass(frozen=True, slots=True)
# @brief Aggregated metrics for one condition within one stage.
# @param stage Stage key.
# @param condition Condition label.
# @param n_trials Number of trials.
# @param metrics Condition-level metrics table.
# @param aggregate Aggregate scalar metrics.
# @param uncertainty Uncertainty metrics.
class ConditionSummary:
    """Aggregated metrics for one condition within one stage."""

    stage: str
    condition: str
    n_trials: int
    metrics: pd.DataFrame
    aggregate: Metrics
    uncertainty: Metrics

    # @brief Convert summary to a flat dictionary row.
    # @param self Instance pointer.
    # @return Flat dictionary representation.
    def to_record(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "condition": self.condition,
            "n_trials": self.n_trials,
            **self.aggregate,
            **{f"uncertainty_{k}": v for k, v in self.uncertainty.items()},
        }


@dataclass(frozen=True, slots=True)
# @brief Inspectable analysis plan built before write side effects.
# @param stage Stage key.
# @param trials Selected trial tuple.
# @param outdir Output directory.
class AnalysisPlan:
    """Inspectable plan of trials to execute before any write side effects."""

    stage: str
    trials: tuple[TrialSpec, ...]
    outdir: Path

    # @brief Convert analysis plan to a serializable dictionary.
    # @param self Instance pointer.
    # @return Plan dictionary.
    def to_record(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "outdir": str(self.outdir),
            "n_trials": len(self.trials),
            "trials": [trial.to_record() for trial in self.trials],
        }


# @brief Base class for user-facing analysis errors.
class HandgripAnalysisError(Exception):
    """Base class for user-facing analysis errors."""


# @brief Error raised when a manifest cannot be normalized or validated.
class ManifestError(HandgripAnalysisError):
    """Raised when a manifest cannot be normalized or validated."""


# @brief Error raised when a requested stage cannot be executed.
class StageExecutionError(HandgripAnalysisError):
    """Raised when a requested stage cannot be executed."""
