"""Configuration loading and validation for Handgrip_Calibration.

The project intentionally uses lightweight dataclasses instead of a heavy schema
framework. The calibration module is meant to be portable for lab PCs, and YAML
configuration is validated just enough to fail early on the mistakes that would
corrupt a calibration session: missing stream names, missing channel mappings,
invalid hold durations, or impossible quality thresholds.
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
    """Static-staircase calibration protocol definition."""

    name: str = "static_staircase_affine_v1"
    warmup_s: float = 0.0
    baseline_duration_s: float = 10.0
    preload_enabled: bool = True
    preload_cycles: int = 3
    preload_max_force_N: float = 100.0
    levels_N: list[float] = field(default_factory=lambda: [0, 10, 20, 40, 60, 80, 100, 80, 60, 40, 20, 10, 0])
    hold_duration_s: float = 5.0
    stable_window_s: float = 3.0
    repeats: int = 2
    prompt_operator: bool = True
    auto_accept_holds: bool = False
    dynamic_slow_ramps: int = 2
    dynamic_fast_squeezes: int = 5

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> "ProtocolConfig":
        data = data or {}
        baseline = data.get("baseline", {}) or {}
        preload = data.get("preload", {}) or {}
        holds = data.get("holds", {}) or {}
        dynamic = data.get("dynamic_validation", {}) or {}
        cfg = cls(
            name=str(data.get("name", cls.name)),
            warmup_s=float(data.get("warmup_s", 0.0)),
            baseline_duration_s=float(baseline.get("duration_s", 10.0)),
            preload_enabled=bool(preload.get("enabled", True)),
            preload_cycles=int(preload.get("cycles", 3)),
            preload_max_force_N=float(preload.get("max_force_N", 100.0)),
            levels_N=[float(x) for x in holds.get("levels_N", cls().levels_N)],
            hold_duration_s=float(holds.get("hold_duration_s", 5.0)),
            stable_window_s=float(holds.get("stable_window_s", 3.0)),
            repeats=int(holds.get("repeats", 2)),
            prompt_operator=bool(data.get("prompt_operator", True)),
            auto_accept_holds=bool(holds.get("auto_accept", False)),
            dynamic_slow_ramps=int(dynamic.get("slow_ramps", 2)),
            dynamic_fast_squeezes=int(dynamic.get("fast_squeezes", 5)),
        )
        cfg.validate()
        return cfg

    def validate(self) -> None:
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


@dataclass(frozen=True)
class FitConfig:
    """Model-fitting and unit-conversion configuration."""

    primary_model: str = "affine"
    target_signal: str = "raw"
    reference_signal: str = "raw"
    reference_scale: float = 1.0
    reference_offset: float = 0.0
    residual_threshold_percent_operating_range: float = 0.5
    operating_range_N: float = 100.0
    weighted_by_reference_noise: bool = False
    export_firmware_constants: bool = True

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> "FitConfig":
        data = data or {}
        cfg = cls(**{k: data.get(k, getattr(cls, k)) for k in cls.__dataclass_fields__})  # type: ignore[arg-type]
        cfg.validate()
        return cfg

    def validate(self) -> None:
        if self.primary_model != "affine":
            raise ConfigError("Only primary_model='affine' is implemented in this release")
        if self.operating_range_N <= 0:
            raise ConfigError("fit.operating_range_N must be > 0")


@dataclass(frozen=True)
class SessionConfig:
    """Top-level session/output configuration."""

    root_dir: Path = Path("data/calibration")
    operator: str = "unknown"
    purpose: str = "affine_handgrip_calibration"
    notes: str = ""
    copy_component_configs: list[Path] = field(default_factory=list)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> "SessionConfig":
        data = data or {}
        return cls(
            root_dir=Path(str(data.get("root_dir", "data/calibration"))).expanduser(),
            operator=str(data.get("operator", "unknown")),
            purpose=str(data.get("purpose", "affine_handgrip_calibration")),
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
