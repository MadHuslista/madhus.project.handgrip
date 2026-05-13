"""Domain models for trial-aware handgrip analysis.

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
class TrialSpec:
    """Validated manifest row describing one capture trial.

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
    def identity(self) -> str:
        """Stable compact identifier used in filenames and tables."""
        return f"{self.stage}__{self.condition}__{self.session_id}__{self.trial_id}"

    def to_record(self) -> dict[str, Any]:
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
class StageConfig:
    """Typed configuration used by stage analyzers.

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
        if "hf_noise_band_hz" in data:
            lo, hi = data["hf_noise_band_hz"]
            data["hf_noise_band_hz"] = (float(lo), float(hi))
        allowed = set(cls.__dataclass_fields__) - {"stage"}
        filtered = {k: v for k, v in data.items() if k in allowed}
        return cls(stage=stage, **filtered)


@dataclass(frozen=True, slots=True)
class TrialResult:
    """Result produced by one stage analyzer for one trial."""

    spec: TrialSpec
    metrics: Metrics
    tables: Mapping[str, pd.DataFrame] = field(default_factory=dict, repr=False, compare=False)
    artifacts: Mapping[str, Path] = field(default_factory=dict)

    def metrics_record(self) -> dict[str, Any]:
        """Flatten trial identity and scalar metrics into one table row."""
        return {**self.spec.to_record(), **self.metrics}


@dataclass(frozen=True, slots=True)
class ConditionSummary:
    """Aggregated metrics for one condition within one stage."""

    stage: str
    condition: str
    n_trials: int
    metrics: pd.DataFrame
    aggregate: Metrics
    uncertainty: Metrics

    def to_record(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "condition": self.condition,
            "n_trials": self.n_trials,
            **self.aggregate,
            **{f"uncertainty_{k}": v for k, v in self.uncertainty.items()},
        }


@dataclass(frozen=True, slots=True)
class AnalysisPlan:
    """Inspectable plan of trials to execute before any write side effects."""

    stage: str
    trials: tuple[TrialSpec, ...]
    outdir: Path

    def to_record(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "outdir": str(self.outdir),
            "n_trials": len(self.trials),
            "trials": [trial.to_record() for trial in self.trials],
        }


class HandgripAnalysisError(Exception):
    """Base class for user-facing analysis errors."""


class ManifestError(HandgripAnalysisError):
    """Raised when a manifest cannot be normalized or validated."""


class StageExecutionError(HandgripAnalysisError):
    """Raised when a requested stage cannot be executed."""
