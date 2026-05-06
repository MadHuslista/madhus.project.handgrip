"""Configuration loading and validation for Handgrip_Calibration.

The project intentionally uses lightweight dataclasses instead of a heavy schema
framework. The calibration module is meant to be portable for lab PCs, and YAML
configuration is validated just enough to fail early on mistakes that would
corrupt a calibration session: missing stream names, missing channel mappings,
invalid hold durations, impossible quality thresholds, or an unsupported fit
candidate name.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import yaml


class ConfigError(ValueError):
    """Raised when a YAML configuration is structurally invalid."""


def _as_list(value: Any) -> list[Any]:
    """Normalize a scalar/list config entry into a list.

    Channel maps accept either a single channel name/index or a list of fallback
    candidates. Lists allow this module to remain compatible with the current
    stream schema while also being ready for the future D2/raw-count schema.
    """

    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


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
    def from_mapping(cls, data: Mapping[str, Any], *, key: str) -> "StreamConfig":
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
            nominal_srate_hz=(None if data.get("nominal_srate_hz") is None else float(data["nominal_srate_hz"])),
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
    def from_mapping(cls, data: Mapping[str, Any] | None) -> "MarkerConfig":
        data = data or {}
        return cls(
            stream_name=str(data.get("stream_name", cls.stream_name)),
            stream_type=str(data.get("stream_type", cls.stream_type)),
            source_id_prefix=str(data.get("source_id_prefix", cls.source_id_prefix)),
            emit_lsl=bool(data.get("emit_lsl", True)),
            write_ndjson=bool(data.get("write_ndjson", True)),
        )


@dataclass(frozen=True)
class ProtocolConfig:
    """Calibration protocol definition.

    The schema remains intentionally lightweight, but it now supports the full
    protocol campaign used by this project:

    - ``reference_verification``: prove the reference path before fitting.
    - ``static_staircase``: primary reversible static-hold calibration.
    - ``low_force_refinement``: optional low-force static ladder.
    - ``creep_zero_return``: stability/drift characterization.
    - ``dynamic_validation``: ramps and squeeze/release stress tests.
    - ``holdout_verification``: independent validation of an existing model.

    Static-style protocols still use ``holds.levels_N`` and are therefore fully
    compatible with the existing segmenter/fitter. Dynamic and creep protocols
    emit explicit markers for post-hoc reporting and do not feed the primary fit.
    """

    name: str = "static_staircase_model_selection_v2"
    protocol_type: str = "static_staircase"
    warmup_s: float = 0.0
    baseline_duration_s: float = 10.0
    preload_enabled: bool = True
    preload_cycles: int = 3
    preload_max_force_N: float = 100.0
    preload_hold_duration_s: float = 0.0
    preload_recovery_duration_s: float = 0.0
    levels_N: list[float] = field(default_factory=lambda: [0, 10, 20, 40, 60, 80, 100, 80, 60, 40, 20, 10, 0])
    hold_duration_s: float = 5.0
    stable_window_s: float = 3.0
    repeats: int = 2
    prompt_operator: bool = True
    auto_accept_holds: bool = False
    dynamic_slow_ramps: int = 2
    dynamic_fast_squeezes: int = 5
    validate_existing_only: bool = False

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> "ProtocolConfig":
        data = data or {}
        baseline = data.get("baseline", {}) or {}
        preload = data.get("preload", {}) or {}
        holds = data.get("holds", {}) or {}
        dynamic = data.get("dynamic_validation", {}) or {}
        name = str(data.get("name", cls.name))
        protocol_type = str(data.get("type", data.get("protocol_type", "")) or "").strip()
        if not protocol_type:
            # Durable inference for older and protocol-specific config names.
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
            preload_enabled=bool(preload.get("enabled", True)),
            preload_cycles=int(preload.get("cycles", 3)),
            preload_max_force_N=float(preload.get("max_force_N", 100.0)),
            preload_hold_duration_s=float(preload.get("hold_duration_s", 0.0)),
            preload_recovery_duration_s=float(preload.get("recovery_duration_s", 0.0)),
            levels_N=[float(x) for x in holds.get("levels_N", cls().levels_N)],
            hold_duration_s=float(holds.get("hold_duration_s", 5.0)),
            stable_window_s=float(holds.get("stable_window_s", 3.0)),
            repeats=int(holds.get("repeats", 2)),
            prompt_operator=bool(data.get("prompt_operator", True)),
            auto_accept_holds=bool(holds.get("auto_accept", False)),
            dynamic_slow_ramps=int(dynamic.get("slow_ramps", dynamic.get("slow_ramp_count", 2))),
            dynamic_fast_squeezes=int(dynamic.get("fast_squeezes", dynamic.get("squeeze_count", 5))),
            validate_existing_only=bool(data.get("validate_existing_only", False) or data.get("mode", "") == "validate_existing_only"),
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
    def from_mapping(cls, data: Mapping[str, Any] | None) -> "QualityConfig":
        data = data or {}
        cfg = cls(**{k: data.get(k, getattr(cls, k)) for k in cls.__dataclass_fields__})  # type: ignore[arg-type]
        cfg.validate()
        return cfg

    def validate(self) -> None:
        if self.reference_min_hz <= 0 or self.reference_expected_hz <= 0:
            raise ConfigError("quality reference rates must be positive")
        if self.reference_max_gap_s <= 0 or self.target_max_gap_s <= 0:
            raise ConfigError("quality max gap thresholds must be positive")
        if self.max_hold_reference_std_N < 0 or self.max_hold_reference_slope_N_per_s < 0:
            raise ConfigError("quality stability thresholds must be non-negative")


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
    """Model-selection policy for candidate calibration models.

    The selector ranks models by cross-validated physical force error, maximum
    absolute error, and a small complexity penalty. This keeps the library from
    promoting nonlinear corrections unless they provide material improvement.
    """

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
    def from_mapping(cls, data: Mapping[str, Any] | None) -> "FitSelectionConfig":
        data = data or {}
        cfg = cls(**{k: data.get(k, getattr(cls, k)) for k in cls.__dataclass_fields__})  # type: ignore[arg-type]
        cfg.validate()
        return cfg

    def validate(self) -> None:
        if self.max_cv_folds < 2:
            raise ConfigError("fit.selection.max_cv_folds must be >= 2")
        if not 0 <= self.min_cv_coverage_fraction <= 1:
            raise ConfigError("fit.selection.min_cv_coverage_fraction must be between 0 and 1")


@dataclass(frozen=True)
class FitRobustConfig:
    """Robust-fit parameters.

    If ``huber_delta_N`` is null, the fitter estimates a residual scale from the
    median absolute deviation of the initial affine residuals and multiplies it
    by ``huber_epsilon``.
    """

    huber_epsilon: float = 1.35
    huber_delta_N: float | None = None
    max_iter: int = 50
    convergence_tol: float = 1e-9
    min_weight: float = 0.05

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> "FitRobustConfig":
        data = data or {}
        cfg = cls(
            huber_epsilon=float(data.get("huber_epsilon", 1.35)),
            huber_delta_N=(None if data.get("huber_delta_N") is None else float(data["huber_delta_N"])),
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
    def from_mapping(cls, data: Mapping[str, Any] | None) -> "FitMultipointConfig":
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
    """Diagnostic model settings.

    Diagnostic models are evaluated and reported but are not automatically
    selected unless ``selection.allow_diagnostics_as_primary`` is true.
    """

    enable_odr_affine: bool = True
    enable_hysteresis: bool = True
    enable_drift: bool = True
    hysteresis_direction_column: str = "direction"
    drift_time_column: str = "t_mid_lsl"

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> "FitDiagnosticsConfig":
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
    candidate_models: list[str] = field(default_factory=lambda: [
        "affine_ols",
        "affine_wls",
        "affine_huber",
        "quadratic_wls",
        "piecewise_linear_monotone",
        "odr_affine",
        "hysteresis_affine_diagnostic",
        "drift_affine_diagnostic",
    ])
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
    def from_mapping(cls, data: Mapping[str, Any] | None) -> "FitConfig":
        data = data or {}
        raw_candidates = data.get("candidate_models")
        if raw_candidates is None:
            # Legacy configs that only had weighted_by_reference_noise still get
            # the full recommended candidate set.
            candidates = cls().candidate_models
        else:
            if not isinstance(raw_candidates, list):
                raise ConfigError("fit.candidate_models must be a list")
            candidates = [str(x) for x in raw_candidates]

        primary_model = str(data.get("primary_model", "auto"))
        if primary_model == "affine":
            # Backward-compatible alias for the original implementation.
            primary_model = "affine_wls" if bool(data.get("weighted_by_reference_noise", True)) else "affine_ols"

        cfg = cls(
            primary_model=primary_model,
            candidate_models=candidates,
            target_signal=str(data.get("target_signal", "raw")),
            reference_signal=str(data.get("reference_signal", "raw")),
            reference_scale=float(data.get("reference_scale", 1.0)),
            reference_offset=float(data.get("reference_offset", 0.0)),
            residual_threshold_percent_operating_range=float(data.get("residual_threshold_percent_operating_range", 0.5)),
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
            raise ConfigError(f"fit.primary_model must be 'auto' or one of {sorted(SUPPORTED_FIT_CANDIDATES)}")
        unknown = sorted(set(self.candidate_models) - SUPPORTED_FIT_CANDIDATES)
        if unknown:
            raise ConfigError(f"Unsupported fit.candidate_models entries: {', '.join(unknown)}")
        if self.operating_range_N <= 0:
            raise ConfigError("fit.operating_range_N must be > 0")
        if self.residual_threshold_percent_operating_range < 0:
            raise ConfigError("fit.residual_threshold_percent_operating_range must be non-negative")
        if self.reference_noise_floor_N <= 0 or self.target_raw_noise_floor <= 0:
            raise ConfigError("fit noise floors must be > 0")


@dataclass(frozen=True)
class SessionConfig:
    """Top-level session/output configuration."""

    root_dir: Path = Path("data/calibration")
    operator: str = "unknown"
    purpose: str = "model_selection_handgrip_calibration"
    notes: str = ""
    copy_component_configs: list[Path] = field(default_factory=list)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> "SessionConfig":
        data = data or {}
        return cls(
            root_dir=Path(str(data.get("root_dir", "data/calibration"))).expanduser(),
            operator=str(data.get("operator", "unknown")),
            purpose=str(data.get("purpose", "model_selection_handgrip_calibration")),
            notes=str(data.get("notes", "")),
            copy_component_configs=[Path(str(p)).expanduser() for p in data.get("copy_component_configs", [])],
        )


@dataclass(frozen=True)
class AppConfig:
    """Complete calibration-module configuration."""

    session: SessionConfig
    streams: dict[str, StreamConfig]
    markers: MarkerConfig
    protocol: ProtocolConfig
    quality: QualityConfig
    fit: FitConfig
    raw: dict[str, Any]

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AppConfig":
        streams_raw = data.get("streams", {})
        if not isinstance(streams_raw, Mapping):
            raise ConfigError("streams must be a mapping")
        missing = [name for name in ("target", "reference") if name not in streams_raw]
        if missing:
            raise ConfigError(f"Missing stream configuration(s): {', '.join(missing)}")
        streams = {key: StreamConfig.from_mapping(value, key=key) for key, value in streams_raw.items()}
        return cls(
            session=SessionConfig.from_mapping(data.get("session")),
            streams=streams,
            markers=MarkerConfig.from_mapping(data.get("markers")),
            protocol=ProtocolConfig.from_mapping(data.get("protocol")),
            quality=QualityConfig.from_mapping(data.get("quality")),
            fit=FitConfig.from_mapping(data.get("fit")),
            raw=dict(data),
        )


def load_config(path: str | Path) -> AppConfig:
    """Load and validate a YAML configuration file."""

    path = Path(path)
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, Mapping):
        raise ConfigError(f"{path} must contain a YAML mapping at the top level")
    return AppConfig.from_dict(data)


def dump_yaml(data: Mapping[str, Any], path: str | Path) -> None:
    """Write a YAML file with stable key order preserved from dictionaries."""

    with Path(path).open("w", encoding="utf-8") as fh:
        yaml.safe_dump(dict(data), fh, sort_keys=False, allow_unicode=True)
