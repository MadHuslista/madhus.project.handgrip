# @package handgrip_calibration.config_schema
#  @brief Configuration loading and validation for Handgrip_Calibration.
"""Configuration loading and validation for Handgrip_Calibration.

All configuration is expressed as immutable, self-validating frozen
dataclasses.  ``load_config()`` uses the Hydra compose API when
``hydra-core`` is installed, falling back to plain ``yaml.safe_load``
for lightweight offline use.

Design principles
-----------------
* No ``AppConfig.raw`` escape hatch.  Every value that the application
  reads is represented by a typed dataclass field.
* ``validate()`` / ``__post_init__`` failures raise ``ConfigError`` so
  mis-configuration is caught early, before any I/O starts.
* Hydra override syntax is supported from the CLI without replacing the
  existing ``argparse`` subcommand structure.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

#: Root of the Handgrip_Calibration package checkout (parent of ``src/``).
#: Used to anchor package-relative defaults (output dir, component config
#: copies, ``conf/`` paths) so the CLI behaves the same whether invoked from
#: the repo root or from within ``Handgrip_Calibration/``.
PACKAGE_ROOT = Path(__file__).resolve().parents[2]


# ──────────────────────────────────────────────────────────────────────────────
# Exceptions
# ──────────────────────────────────────────────────────────────────────────────


class ConfigError(ValueError):
    """Raised when a YAML configuration is structurally invalid."""


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _as_list(value: Any) -> list[Any]:
    """Normalise a scalar/list config entry into a list.

    Channel maps accept either a single channel name/index or a list of
    fallback candidates.
    """
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


# ──────────────────────────────────────────────────────────────────────────────
# Stream & marker configs
# ──────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class StreamConfig:
    """Description of a stream consumed by the calibration module."""

    name: str
    stream_type: str | None = None
    source_id: str | None = None
    timeout_s: float = 5.0
    channel_map: dict[str, list[str | int]] = field(default_factory=dict)
    nominal_srate_hz: float | None = None
    required: bool = True

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any], *, key: str) -> StreamConfig:
        # @brief Build a stream configuration object from a mapping.
        #  @param cls StreamConfig class.
        #  @param data Stream configuration mapping.
        #  @param key Stream key used for validation messages.
        #  @return Validated StreamConfig instance.
        if not isinstance(data, Mapping):
            raise ConfigError(f"streams.{key} must be a mapping")
        name = data.get("name")
        if not name:
            raise ConfigError(f"streams.{key}.name is required")
        channel_map_raw = data.get("channel_map", {}) or {}
        if not isinstance(channel_map_raw, Mapping):
            raise ConfigError(f"streams.{key}.channel_map must be a mapping")
        channel_map = {str(k): _as_list(v) for k, v in channel_map_raw.items()}
        return cls(
            name=str(name),
            stream_type=data.get("type"),
            source_id=data.get("source_id"),
            timeout_s=float(data.get("timeout_s", 5.0)),
            channel_map=channel_map,
            nominal_srate_hz=(
                None if data.get("nominal_srate_hz") is None else float(data["nominal_srate_hz"])
            ),
            required=bool(data.get("required", True)),
        )


@dataclass(frozen=True)
class MarkerConfig:
    """Configuration for the calibration marker stream and event log."""

    stream_name: str = "HandgripCalibrationMarkers"
    stream_type: str = "Markers"
    source_id_prefix: str = "handgrip-calibration"
    emit_lsl: bool = True
    write_ndjson: bool = True

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> MarkerConfig:
        # @brief Build marker configuration from a mapping.
        #  @param cls MarkerConfig class.
        #  @param data Marker configuration mapping or None.
        #  @return Validated MarkerConfig instance.
        data = data or {}
        return cls(
            stream_name=str(data.get("stream_name", cls.stream_name)),
            stream_type=str(data.get("stream_type", cls.stream_type)),
            source_id_prefix=str(data.get("source_id_prefix", cls.source_id_prefix)),
            emit_lsl=bool(data.get("emit_lsl", True)),
            write_ndjson=bool(data.get("write_ndjson", True)),
        )


# ──────────────────────────────────────────────────────────────────────────────
# Protocol config
# ──────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ProtocolConfig:
    """Calibration protocol definition.

    Supports the full protocol campaign:

    * ``reference_verification``
    * ``static_staircase``
    * ``low_force_refinement``
    * ``creep_zero_return``
    * ``dynamic_validation``
    * ``holdout_verification``
    """

    name: str = "static_staircase_model_selection_v2"
    protocol_type: str = "static_staircase"
    warmup_s: float = 0.0
    baseline_duration_s: float = 10.0
    baseline_require_stable: bool = True
    preload_enabled: bool = True
    preload_cycles: int = 3
    preload_max_force_N: float = 100.0
    preload_hold_duration_s: float = 0.0
    preload_recovery_duration_s: float = 0.0
    levels_N: list[float] = field(
        default_factory=lambda: [0, 10, 20, 40, 60, 80, 100, 80, 60, 40, 20, 10, 0]
    )
    hold_duration_s: float = 5.0
    stable_window_s: float = 3.0
    repeats: int = 2
    prompt_operator: bool = True
    auto_accept_holds: bool = False
    dynamic_slow_ramps: int = 2
    dynamic_fast_squeezes: int = 5
    validate_existing_only: bool = False

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> ProtocolConfig:
        data = data or {}
        baseline = data.get("baseline", {}) or {}
        preload = data.get("preload", {}) or {}
        holds = data.get("holds", {}) or {}
        dynamic = data.get("dynamic_validation", {}) or {}
        name = str(data.get("name", cls.name))
        protocol_type = str(data.get("type", data.get("protocol_type", "")) or "").strip()
        if not protocol_type:
            lowered = name.lower()
            if "reference" in lowered and "verification" in lowered:
                protocol_type = "reference_verification"
            elif "low_force" in lowered:
                protocol_type = "low_force_refinement"
            elif "creep" in lowered or "zero_return" in lowered:
                protocol_type = "creep_zero_return"
            elif "dynamic" in lowered or "ramp" in lowered or "squeeze" in lowered:
                protocol_type = "dynamic_validation"
            elif "holdout" in lowered or "verification" in lowered:
                protocol_type = "holdout_verification"
            else:
                protocol_type = "static_staircase"
        cfg = cls(
            name=name,
            protocol_type=protocol_type,
            warmup_s=float(data.get("warmup_s", 0.0)),
            baseline_duration_s=float(baseline.get("duration_s", 10.0)),
            baseline_require_stable=bool(baseline.get("require_stable", True)),
            preload_enabled=bool(preload.get("enabled", True)),
            preload_cycles=int(preload.get("cycles", 3)),
            preload_max_force_N=float(preload.get("max_force_N", 100.0)),
            preload_hold_duration_s=float(preload.get("hold_duration_s", 0.0)),
            preload_recovery_duration_s=float(preload.get("recovery_duration_s", 0.0)),
            levels_N=[
                float(x)
                for x in holds.get(
                    "levels_N", cls.__dataclass_fields__["levels_N"].default_factory()
                )
            ],  # type: ignore[misc]
            hold_duration_s=float(holds.get("hold_duration_s", 5.0)),
            stable_window_s=float(holds.get("stable_window_s", 3.0)),
            repeats=int(holds.get("repeats", 2)),
            prompt_operator=bool(data.get("prompt_operator", True)),
            auto_accept_holds=bool(holds.get("auto_accept", False)),
            dynamic_slow_ramps=int(dynamic.get("slow_ramps", dynamic.get("slow_ramp_count", 2))),
            dynamic_fast_squeezes=int(
                dynamic.get("fast_squeezes", dynamic.get("squeeze_count", 5))
            ),
            validate_existing_only=bool(
                data.get("validate_existing_only", False)
                or data.get("mode", "") == "validate_existing_only"
            ),
        )
        cfg.validate()
        return cfg

    def validate(self) -> None:
        allowed_types = {
            "reference_verification",
            "static_staircase",
            "low_force_refinement",
            "creep_zero_return",
            "dynamic_validation",
            "holdout_verification",
        }
        if self.protocol_type not in allowed_types:
            raise ConfigError(f"protocol.type must be one of {sorted(allowed_types)}")
        if not self.levels_N:
            raise ConfigError("protocol.holds.levels_N must contain at least one level")
        if self.hold_duration_s <= 0:
            raise ConfigError("protocol.holds.hold_duration_s must be > 0")
        if self.stable_window_s <= 0 or self.stable_window_s > self.hold_duration_s:
            raise ConfigError("protocol.holds.stable_window_s must be > 0 and <= hold_duration_s")
        if self.repeats < 1:
            raise ConfigError("protocol.holds.repeats must be >= 1")
        if self.baseline_duration_s <= 0:
            raise ConfigError("protocol.baseline.duration_s must be > 0")
        if self.preload_cycles < 0:
            raise ConfigError("protocol.preload.cycles must be >= 0")
        if self.preload_hold_duration_s < 0 or self.preload_recovery_duration_s < 0:
            raise ConfigError("protocol.preload hold/recovery durations must be >= 0")
        if self.dynamic_slow_ramps < 0 or self.dynamic_fast_squeezes < 0:
            raise ConfigError("protocol.dynamic_validation counts must be >= 0")


# ──────────────────────────────────────────────────────────────────────────────
# Creep / zero-return config  (was AppConfig.raw["protocol"]["creep_zero_return"])
# ──────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CreepZeroReturnConfig:
    """Creep/zero-return characterisation sub-protocol settings.

    Previously accessed via the un-validated ``AppConfig.raw`` escape
    hatch.  Now a first-class, validated configuration object.
    """

    force_levels_N: list[float] = field(default_factory=lambda: [0.0, 80.0, 0.0])
    durations_s: list[float] = field(default_factory=lambda: [120.0, 300.0, 300.0])
    read_times_s: list[float] = field(default_factory=lambda: [30.0, 300.0])

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> CreepZeroReturnConfig:
        data = data or {}
        defaults = cls()
        force_levels = [float(x) for x in data.get("force_levels_N", defaults.force_levels_N)]
        durations = [float(x) for x in data.get("durations_s", defaults.durations_s)]
        read_times = sorted(
            float(x) for x in data.get("read_times_s", defaults.read_times_s) if float(x) >= 0
        )
        cfg = cls(
            force_levels_N=force_levels,
            durations_s=durations,
            read_times_s=read_times,
        )
        cfg.validate()
        return cfg

    def validate(self) -> None:
        if not self.force_levels_N:
            raise ConfigError("creep.force_levels_N must not be empty")
        if len(self.durations_s) < len(self.force_levels_N):
            raise ConfigError(
                "creep.durations_s must have at least as many entries as force_levels_N"
            )
        if any(d < 0 for d in self.durations_s):
            raise ConfigError("creep.durations_s values must be >= 0")


# ──────────────────────────────────────────────────────────────────────────────
# Dynamic validation config  (was AppConfig.raw["protocol"]["dynamic_validation"])
# ──────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RampSpec:
    """Specification for one ramp group in the dynamic validation protocol."""

    label: str = "slow"
    count: int = 2
    peak_force_N: float = 100.0
    speed_N_per_s: float = 5.0

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> RampSpec:
        return cls(
            label=str(data.get("label", "slow")),
            count=int(data.get("count", 0)),
            peak_force_N=float(data.get("peak_force_N", 100.0)),
            speed_N_per_s=float(data.get("speed_N_per_s", 5.0)),
        )


@dataclass(frozen=True)
class SqueezeSpec:
    """Specification for one squeeze group in the dynamic validation protocol."""

    label: str = "fast_squeeze"
    count: int = 5
    peak_force_N: float = 100.0
    rest_s: float = 3.0

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> SqueezeSpec:
        return cls(
            label=str(data.get("label", "fast_squeeze")),
            count=int(data.get("count", 0)),
            peak_force_N=float(data.get("peak_force_N", 100.0)),
            rest_s=float(data.get("rest_s", 3.0)),
        )


@dataclass(frozen=True)
class DynamicValidationConfig:
    """Dynamic validation sub-protocol settings.

    Previously accessed via the un-validated ``AppConfig.raw`` escape
    hatch.  Now a first-class, validated configuration object.
    """

    ramps: list[RampSpec] = field(
        default_factory=lambda: [
            RampSpec(label="slow", count=2, peak_force_N=100.0, speed_N_per_s=5.0),
            RampSpec(label="medium", count=0, peak_force_N=100.0, speed_N_per_s=20.0),
        ]
    )
    squeezes: list[SqueezeSpec] = field(
        default_factory=lambda: [
            SqueezeSpec(label="fast_squeeze", count=5, peak_force_N=100.0, rest_s=3.0),
        ]
    )

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> DynamicValidationConfig:
        data = data or {}
        defaults = cls()
        ramp_list = data.get("ramps")
        squeezes_list = data.get("squeezes")
        ramps = (
            [RampSpec.from_mapping(r) for r in ramp_list]
            if ramp_list is not None
            else defaults.ramps
        )
        squeezes = (
            [SqueezeSpec.from_mapping(s) for s in squeezes_list]
            if squeezes_list is not None
            else defaults.squeezes
        )
        cfg = cls(ramps=ramps, squeezes=squeezes)
        cfg.validate()
        return cfg

    def validate(self) -> None:
        for ramp in self.ramps:
            if ramp.count < 0:
                raise ConfigError("dynamic.ramps[].count must be >= 0")
            if ramp.peak_force_N <= 0:
                raise ConfigError("dynamic.ramps[].peak_force_N must be > 0")
        for squeeze in self.squeezes:
            if squeeze.count < 0:
                raise ConfigError("dynamic.squeezes[].count must be >= 0")
            if squeeze.rest_s < 0:
                raise ConfigError("dynamic.squeezes[].rest_s must be >= 0")


# ──────────────────────────────────────────────────────────────────────────────
# Holdout validation thresholds  (was AppConfig.raw["validation"]["holdout"])
# ──────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class HoldoutValidationThresholds:
    """Release-gate thresholds for holdout validation.

    ``None`` values are derived at runtime from
    ``FitConfig.operating_range_N`` when not explicitly configured.

    Previously accessed via the un-validated ``AppConfig.raw`` escape
    hatch.  Now a first-class, validated configuration object.
    """

    max_rmse_N: float | None = None
    max_abs_error_N: float | None = None
    max_bias_N: float | None = None

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> HoldoutValidationThresholds:
        data = data or {}

        def _opt_float(key: str) -> float | None:
            val = data.get(key)
            return float(val) if val is not None else None

        return cls(
            max_rmse_N=_opt_float("max_rmse_N"),
            max_abs_error_N=_opt_float("max_abs_error_N"),
            max_bias_N=_opt_float("max_bias_N"),
        )


# ──────────────────────────────────────────────────────────────────────────────
# Quality config
# ──────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class QualityConfig:
    """Quality thresholds used for live warnings and offline hold rejection."""

    reference_expected_hz: float = 500.0
    reference_min_hz: float = 495.0
    reference_max_gap_s: float = 0.020
    target_expected_hz_min: float = 85.0
    target_expected_hz_max: float = 105.0
    target_max_gap_s: float = 0.100
    max_hold_reference_std_N: float = 0.5
    max_hold_reference_slope_N_per_s: float = 0.2
    max_baseline_drift_N_per_min: float = 0.5
    min_hold_target_samples: int = 20
    min_hold_reference_samples: int = 100
    quality_emit_period_s: float = 1.0

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> QualityConfig:
        data = data or {}
        cfg = cls(
            **{k: data.get(k, getattr(cls, k)) for k in cls.__dataclass_fields__}  # type: ignore[arg-type]
        )
        cfg.validate()
        return cfg

    def validate(self) -> None:
        if self.reference_min_hz <= 0 or self.reference_expected_hz <= 0:
            raise ConfigError("quality reference rates must be positive")
        if self.reference_max_gap_s <= 0 or self.target_max_gap_s <= 0:
            raise ConfigError("quality max gap thresholds must be positive")
        if self.max_hold_reference_std_N < 0 or self.max_hold_reference_slope_N_per_s < 0:
            raise ConfigError("quality stability thresholds must be non-negative")


# ──────────────────────────────────────────────────────────────────────────────
# Fit configs
# ──────────────────────────────────────────────────────────────────────────────


SUPPORTED_FIT_CANDIDATES = {
    "affine_ols",
    "affine_wls",
    "affine_huber",
    "quadratic_wls",
    "piecewise_linear_monotone",
    "odr_affine",
    "hysteresis_affine_diagnostic",
    "drift_affine_diagnostic",
}


@dataclass(frozen=True)
class FitSelectionConfig:
    """Model-selection policy for candidate calibration models."""

    primary_metric: str = "cv_rmse_N"
    max_error_metric: str = "max_abs_error_percent_range"
    prefer_simpler_within_cv_rmse_se: bool = True
    require_monotonic: bool = True
    allow_diagnostics_as_primary: bool = False
    cv_group_by: str = "target_force_nominal_N"
    max_cv_folds: int = 12
    alpha_cv_rmse: float = 40.0
    beta_max_error: float = 60.0
    lambda_complexity: float = 0.15
    monotonicity_violation_penalty: float = 10.0
    diagnostic_model_penalty: float = 2.0
    min_cv_coverage_fraction: float = 0.50

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> FitSelectionConfig:
        data = data or {}
        cfg = cls(
            **{k: data.get(k, getattr(cls, k)) for k in cls.__dataclass_fields__}  # type: ignore[arg-type]
        )
        cfg.validate()
        return cfg

    def validate(self) -> None:
        if self.max_cv_folds < 2:
            raise ConfigError("fit.selection.max_cv_folds must be >= 2")
        if not 0 <= self.min_cv_coverage_fraction <= 1:
            raise ConfigError("fit.selection.min_cv_coverage_fraction must be between 0 and 1")


@dataclass(frozen=True)
class FitRobustConfig:
    """Robust-fit parameters."""

    huber_epsilon: float = 1.35
    huber_delta_N: float | None = None
    max_iter: int = 50
    convergence_tol: float = 1e-9
    min_weight: float = 0.05

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> FitRobustConfig:
        data = data or {}
        cfg = cls(
            huber_epsilon=float(data.get("huber_epsilon", 1.35)),
            huber_delta_N=(
                None if data.get("huber_delta_N") is None else float(data["huber_delta_N"])
            ),
            max_iter=int(data.get("max_iter", 50)),
            convergence_tol=float(data.get("convergence_tol", 1e-9)),
            min_weight=float(data.get("min_weight", 0.05)),
        )
        cfg.validate()
        return cfg

    def validate(self) -> None:
        if self.huber_epsilon <= 0:
            raise ConfigError("fit.robust.huber_epsilon must be > 0")
        if self.max_iter < 1:
            raise ConfigError("fit.robust.max_iter must be >= 1")
        if not 0 < self.min_weight <= 1:
            raise ConfigError("fit.robust.min_weight must be in (0, 1]")


@dataclass(frozen=True)
class FitMultipointConfig:
    """Monotone multipoint correction settings."""

    min_points: int = 5
    interpolation: str = "piecewise_linear"
    extrapolation: str = "reject"
    aggregate_by: str = "target_force_nominal_N"
    max_knots: int = 12

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> FitMultipointConfig:
        data = data or {}
        cfg = cls(
            min_points=int(data.get("min_points", 5)),
            interpolation=str(data.get("interpolation", "piecewise_linear")),
            extrapolation=str(data.get("extrapolation", "reject")),
            aggregate_by=str(data.get("aggregate_by", "target_force_nominal_N")),
            max_knots=int(data.get("max_knots", 12)),
        )
        cfg.validate()
        return cfg

    def validate(self) -> None:
        if self.min_points < 3:
            raise ConfigError("fit.multipoint.min_points must be >= 3")
        if self.interpolation not in {"piecewise_linear"}:
            raise ConfigError("Only fit.multipoint.interpolation='piecewise_linear' is implemented")
        if self.extrapolation not in {"reject", "clip"}:
            raise ConfigError("fit.multipoint.extrapolation must be 'reject' or 'clip'")
        if self.max_knots < self.min_points:
            raise ConfigError("fit.multipoint.max_knots must be >= min_points")


@dataclass(frozen=True)
class FitDiagnosticsConfig:
    """Diagnostic model settings."""

    enable_odr_affine: bool = True
    enable_hysteresis: bool = True
    enable_drift: bool = True
    hysteresis_direction_column: str = "direction"
    drift_time_column: str = "t_mid_lsl"

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> FitDiagnosticsConfig:
        data = data or {}
        return cls(
            enable_odr_affine=bool(data.get("enable_odr_affine", True)),
            enable_hysteresis=bool(data.get("enable_hysteresis", True)),
            enable_drift=bool(data.get("enable_drift", True)),
            hysteresis_direction_column=str(data.get("hysteresis_direction_column", "direction")),
            drift_time_column=str(data.get("drift_time_column", "t_mid_lsl")),
        )


@dataclass(frozen=True)
class FitConfig:
    """Model-fitting and unit-conversion configuration."""

    primary_model: str = "auto"
    candidate_models: list[str] = field(
        default_factory=lambda: [
            "affine_ols",
            "affine_wls",
            "affine_huber",
            "quadratic_wls",
            "piecewise_linear_monotone",
            "odr_affine",
            "hysteresis_affine_diagnostic",
            "drift_affine_diagnostic",
        ]
    )
    target_signal: str = "raw"
    reference_signal: str = "raw"
    reference_scale: float = 1.0
    reference_offset: float = 0.0
    residual_threshold_percent_operating_range: float = 0.5
    operating_range_N: float = 100.0
    weighted_by_reference_noise: bool = True
    reference_noise_floor_N: float = 0.05
    target_raw_noise_floor: float = 1.0
    export_firmware_constants: bool = True
    selection: FitSelectionConfig = field(default_factory=FitSelectionConfig)
    robust: FitRobustConfig = field(default_factory=FitRobustConfig)
    multipoint: FitMultipointConfig = field(default_factory=FitMultipointConfig)
    diagnostics: FitDiagnosticsConfig = field(default_factory=FitDiagnosticsConfig)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> FitConfig:
        data = data or {}
        raw_candidates = data.get("candidate_models")
        if raw_candidates is None:
            candidates = cls.__dataclass_fields__["candidate_models"].default_factory()  # type: ignore[misc]
        else:
            if not isinstance(raw_candidates, list):
                raise ConfigError("fit.candidate_models must be a list")
            candidates = [str(x) for x in raw_candidates]

        primary_model = str(data.get("primary_model", "auto"))
        if primary_model == "affine":
            # Backward-compatible alias — emit deprecation notice via logging
            primary_model = (
                "affine_wls"
                if bool(data.get("weighted_by_reference_noise", True))
                else "affine_ols"
            )
            log.warning(
                "fit.primary_model='affine' is deprecated. "
                "Set 'affine_wls' or 'affine_ols' explicitly."
            )

        cfg = cls(
            primary_model=primary_model,
            candidate_models=candidates,
            target_signal=str(data.get("target_signal", "raw")),
            reference_signal=str(data.get("reference_signal", "raw")),
            reference_scale=float(data.get("reference_scale", 1.0)),
            reference_offset=float(data.get("reference_offset", 0.0)),
            residual_threshold_percent_operating_range=float(
                data.get("residual_threshold_percent_operating_range", 0.5)
            ),
            operating_range_N=float(data.get("operating_range_N", 100.0)),
            weighted_by_reference_noise=bool(data.get("weighted_by_reference_noise", True)),
            reference_noise_floor_N=float(data.get("reference_noise_floor_N", 0.05)),
            target_raw_noise_floor=float(data.get("target_raw_noise_floor", 1.0)),
            export_firmware_constants=bool(data.get("export_firmware_constants", True)),
            selection=FitSelectionConfig.from_mapping(data.get("selection")),
            robust=FitRobustConfig.from_mapping(data.get("robust")),
            multipoint=FitMultipointConfig.from_mapping(data.get("multipoint")),
            diagnostics=FitDiagnosticsConfig.from_mapping(data.get("diagnostics")),
        )
        cfg.validate()
        return cfg

    def validate(self) -> None:
        allowed_primary = {"auto", *SUPPORTED_FIT_CANDIDATES}
        if self.primary_model not in allowed_primary:
            raise ConfigError(
                f"fit.primary_model must be 'auto' or one of {sorted(SUPPORTED_FIT_CANDIDATES)}"
            )
        unknown = sorted(set(self.candidate_models) - SUPPORTED_FIT_CANDIDATES)
        if unknown:
            raise ConfigError(f"Unsupported fit.candidate_models entries: {', '.join(unknown)}")
        if self.operating_range_N <= 0:
            raise ConfigError("fit.operating_range_N must be > 0")
        if self.residual_threshold_percent_operating_range < 0:
            raise ConfigError("fit.residual_threshold_percent_operating_range must be non-negative")
        if self.reference_noise_floor_N <= 0 or self.target_raw_noise_floor <= 0:
            raise ConfigError("fit noise floors must be > 0")



# ──────────────────────────────────────────────────────────────────────────────
# Calibration artifact compensation
# ──────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CalibrationArtifactWindowConfig:
    """Window selection for optional fixture-artifact compensation."""

    source: str = "stable_window"
    tail_s: float = 2.0

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> CalibrationArtifactWindowConfig:
        data = data or {}
        cfg = cls(source=str(data.get("source", "stable_window")), tail_s=float(data.get("tail_s", 2.0)))
        cfg.validate()
        return cfg

    def validate(self) -> None:
        if self.source != "stable_window":
            raise ConfigError("calibration_artifact.window.source must be 'stable_window'")
        if self.tail_s <= 0:
            raise ConfigError("calibration_artifact.window.tail_s must be > 0")


@dataclass(frozen=True)
class CalibrationArtifactGroupingConfig:
    """Grouping/outlier policy for optional artifact compensation."""

    require_both_directions: bool = True
    outlier_method: str = "mad"
    max_mad_z: float = 3.5

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> CalibrationArtifactGroupingConfig:
        data = data or {}
        cfg = cls(
            require_both_directions=bool(data.get("require_both_directions", True)),
            outlier_method=str(data.get("outlier_method", "mad")),
            max_mad_z=float(data.get("max_mad_z", 3.5)),
        )
        cfg.validate()
        return cfg

    def validate(self) -> None:
        if self.outlier_method != "mad":
            raise ConfigError("calibration_artifact.grouping.outlier_method must be 'mad'")
        if self.max_mad_z <= 0:
            raise ConfigError("calibration_artifact.grouping.max_mad_z must be > 0")


@dataclass(frozen=True)
class CalibrationArtifactConfig:
    """Optional, removable compensation for fixture-induced hold relaxation.

    This is intended for calibration sessions where the PM58 reference and
    handgrip target share a mechanically contaminated load path during static
    staircases.  It never changes firmware behavior; it only changes the offline
    fit dataset when explicitly enabled.
    """

    enabled: bool = False
    mode: str = "direction_balanced_tail_median"
    window: CalibrationArtifactWindowConfig = field(default_factory=CalibrationArtifactWindowConfig)
    grouping: CalibrationArtifactGroupingConfig = field(default_factory=CalibrationArtifactGroupingConfig)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> CalibrationArtifactConfig:
        data = data or {}
        cfg = cls(
            enabled=bool(data.get("enabled", False)),
            mode=str(data.get("mode", "direction_balanced_tail_median")),
            window=CalibrationArtifactWindowConfig.from_mapping(data.get("window")),
            grouping=CalibrationArtifactGroupingConfig.from_mapping(data.get("grouping")),
        )
        cfg.validate()
        return cfg

    def validate(self) -> None:
        if self.mode != "direction_balanced_tail_median":
            raise ConfigError(
                "calibration_artifact.mode must be 'direction_balanced_tail_median'"
            )


# ──────────────────────────────────────────────────────────────────────────────
# Session config
# ──────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SessionConfig:
    """Top-level session/output configuration."""

    root_dir: Path = Path("data/calibration")
    operator: str = "unknown"
    purpose: str = "model_selection_handgrip_calibration"
    notes: str = ""
    copy_component_configs: list[Path] = field(default_factory=list)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> SessionConfig:
        data = data or {}
        root_dir = Path(str(data.get("root_dir", "data/calibration"))).expanduser()
        if not root_dir.is_absolute():
            root_dir = PACKAGE_ROOT / root_dir
        copy_component_configs = []
        for p in data.get("copy_component_configs", []):
            cfg_path = Path(str(p)).expanduser()
            if not cfg_path.is_absolute():
                cfg_path = PACKAGE_ROOT / cfg_path
            copy_component_configs.append(cfg_path)
        return cls(
            root_dir=root_dir,
            operator=str(data.get("operator", "unknown")),
            purpose=str(data.get("purpose", "model_selection_handgrip_calibration")),
            notes=str(data.get("notes", "")),
            copy_component_configs=copy_component_configs,
        )


# ──────────────────────────────────────────────────────────────────────────────
# Top-level AppConfig  (AppConfig.raw removed)
# ──────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AppConfig:
    """Complete calibration-module configuration.

    All previously un-validated sub-configs that were accessed through
    ``AppConfig.raw`` are now typed fields: ``creep``, ``dynamic``, and
    ``holdout_thresholds``.
    """

    session: SessionConfig
    streams: dict[str, StreamConfig]
    markers: MarkerConfig
    protocol: ProtocolConfig
    quality: QualityConfig
    fit: FitConfig
    calibration_artifact: CalibrationArtifactConfig
    creep: CreepZeroReturnConfig
    dynamic: DynamicValidationConfig
    holdout_thresholds: HoldoutValidationThresholds

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> AppConfig:
        streams_raw = data.get("streams", {})
        if not isinstance(streams_raw, Mapping):
            raise ConfigError("streams must be a mapping")
        missing = [n for n in ("target", "reference") if n not in streams_raw]
        if missing:
            raise ConfigError(f"Missing stream configuration(s): {', '.join(missing)}")
        streams = {
            key: StreamConfig.from_mapping(value, key=key) for key, value in streams_raw.items()
        }
        return cls(
            session=SessionConfig.from_mapping(data.get("session")),
            streams=streams,
            markers=MarkerConfig.from_mapping(data.get("markers")),
            protocol=ProtocolConfig.from_mapping(data.get("protocol")),
            quality=QualityConfig.from_mapping(data.get("quality")),
            fit=FitConfig.from_mapping(data.get("fit")),
            calibration_artifact=CalibrationArtifactConfig.from_mapping(
                data.get("calibration_artifact")
            ),
            creep=CreepZeroReturnConfig.from_mapping(data.get("creep")),
            dynamic=DynamicValidationConfig.from_mapping(data.get("dynamic")),
            holdout_thresholds=HoldoutValidationThresholds.from_mapping(
                data.get("holdout_thresholds")
            ),
        )


# ──────────────────────────────────────────────────────────────────────────────
# Config loading (Hydra compose API with PyYAML fallback)
# ──────────────────────────────────────────────────────────────────────────────


def load_config(path: str | Path) -> AppConfig:
    # @brief Load and validate an application YAML configuration.
    #  @param path Path to the YAML configuration file.
    #  @return Validated application configuration object.
    """Load and validate a YAML configuration file.

    Uses the Hydra compose API when ``hydra-core`` is installed so that
    Hydra override syntax is available from the CLI.  Falls back to plain
    ``yaml.safe_load`` when Hydra is unavailable (lightweight embedded use).

    Parameters
    ----------
    path:
        Path to the YAML config file.  When using Hydra, the parent
        directory becomes the config search path and the file stem is the
        config name.
    """
    path = Path(path)
    if not path.is_absolute() and not path.exists() and (PACKAGE_ROOT / path).exists():
        path = PACKAGE_ROOT / path
    path = path.resolve()

    data: dict[str, Any]
    try:
        from hydra import compose, initialize_config_dir
        from hydra.core.global_hydra import GlobalHydra
        from omegaconf import OmegaConf

        # Clear any residual Hydra state from previous calls (test isolation).
        GlobalHydra.instance().clear()

        with initialize_config_dir(
            config_dir=str(path.parent),
            version_base="1.3",
        ):
            raw_cfg = compose(config_name=path.stem)
            data = OmegaConf.to_container(raw_cfg, resolve=True, throw_on_missing=False)  # type: ignore[assignment]
        log.debug("Config loaded via Hydra compose API from %s", path)

    except ImportError:
        import yaml

        log.debug("hydra-core not available; loading %s via yaml.safe_load", path)
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}

    if not isinstance(data, Mapping):
        raise ConfigError(f"{path} must contain a YAML mapping at the top level")
    return AppConfig.from_dict(data)


def resolve_session_dir(path: str | Path) -> Path:
    # @brief Resolve a session directory argument, cwd-first with a
    #  Handgrip_Calibration/-relative fallback.
    #  @param path Session directory as given on the CLI.
    #  @return Absolute Path to the session directory.
    """Resolve a ``session_dir`` CLI argument.

    Relative paths are resolved against the current working directory first
    (preserving existing behavior). If that location doesn't exist, fall back
    to resolving against ``PACKAGE_ROOT`` (the ``Handgrip_Calibration/``
    directory), so paths like ``data/calibration/<session_id>`` work the same
    whether the command is run from the repo root or from within
    ``Handgrip_Calibration/``.
    """
    session_dir = Path(path)
    if not session_dir.is_absolute() and not session_dir.exists():
        fallback = PACKAGE_ROOT / session_dir
        if fallback.exists():
            session_dir = fallback
    return session_dir.resolve()


def dump_yaml(data: Mapping[str, Any], path: str | Path) -> None:
    # @brief Dump a mapping to YAML with stable key order.
    #  @param data Mapping data to serialize.
    #  @param path Output YAML file path.
    """Write a YAML file with stable key order."""
    import yaml

    with Path(path).open("w", encoding="utf-8") as fh:
        yaml.safe_dump(dict(data), fh, sort_keys=False, allow_unicode=True)
