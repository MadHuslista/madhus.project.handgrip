# @file
# @brief Structured Hydra configuration schema for the handgrip realtime viewer.
##
# Each @dataclass here corresponds to a section of conf/config.yaml.
# Registering these with ConfigStore gives Hydra full type awareness:
# attribute access is IDE-navigable, defaults are declared once, and
# no OmegaConf.select() calls with inline defaults are needed.
##
# @note Call register_config() once at module import time in cli.py, before
# the @hydra.main decorator is evaluated.

from __future__ import annotations

from dataclasses import dataclass, field

from hydra.core.config_store import ConfigStore
from omegaconf import MISSING

# ---------------------------------------------------------------------------
# Stream configuration
# ---------------------------------------------------------------------------


@dataclass
class TargetStreamCfg:
    # @brief Configuration for the target LSL stream.
    name: str = MISSING
    stype: str = MISSING
    source_id: str | None = None
    buffer_samples: int = 1600
    acquisition_delay: float = 0.01
    timeout: float = 5.0


@dataclass
class ReferenceStreamCfg:
    # @brief Configuration for the reference LSL stream.
    name: str = MISSING
    stype: str = MISSING
    source_id: str | None = None
    buffer_seconds: float = 12.0
    acquisition_delay: float = 0.01
    timeout: float = 5.0
    expected_rate_hz: float = 500.0


@dataclass
class StreamsCfg:
    # @brief Container for target and reference stream settings.
    target: TargetStreamCfg = field(default_factory=TargetStreamCfg)
    reference: ReferenceStreamCfg = field(default_factory=ReferenceStreamCfg)


# ---------------------------------------------------------------------------
# Channel label configuration
# ---------------------------------------------------------------------------


@dataclass
class TargetChannelCfg:
    # @brief Channel labels used by the target stream.
    clock_label: str = "device_clock_us"
    raw_label: str = "target_raw_count"
    filtered_label: str = "target_filtered_units"


@dataclass
class ReferenceChannelCfg:
    # @brief Channel labels used by the reference stream.
    clock_label: str = "reference_clock_s"
    raw_label: str = "reference_force_N"


@dataclass
class ChannelsCfg:
    # @brief Container for target and reference channel labels.
    target: TargetChannelCfg = field(default_factory=TargetChannelCfg)
    reference: ReferenceChannelCfg = field(default_factory=ReferenceChannelCfg)


# ---------------------------------------------------------------------------
# Visual style (replaces module-level color globals)
# ---------------------------------------------------------------------------


@dataclass
class StyleCfg:
    # @brief Visual constants previously hardcoded as module-level globals.

    raw_color: str = "red"
    filtered_color: str = "green"
    reference_color: str = "purple"
    timing_color: str = "blue"
    grid_alpha: float = 0.3
    xy_color: str = "red"
    xy_alpha_old: float = 0.12
    xy_alpha_new: float = 0.92
    xy_line_width: float = 1.6


# ---------------------------------------------------------------------------
# XY correlation / time alignment
# ---------------------------------------------------------------------------


@dataclass
class TimeAlignmentCfg:
    # @brief Time-alignment policy for XY correlation.
    mode: str = "raw_lsl"  # raw_lsl | tail_aligned_lsl | manual
    manual_reference_shift_s: float = 0.0
    max_auto_shift_s: float | None = None
    min_auto_shift_s: float = 0.0
    snap_threshold_s: float = 0.250
    smoothing_alpha: float = 1.0


@dataclass
class XYCorrelationCfg:
    # @brief Settings for the XY correlation display.
    lock_max_span: bool = False
    toggle_key: str = "x"
    target_signal: str = "raw"  # raw | filtered
    time_alignment: TimeAlignmentCfg = field(default_factory=TimeAlignmentCfg)


# ---------------------------------------------------------------------------
# Interactive controls
# ---------------------------------------------------------------------------


@dataclass
class ControlsCfg:
    # @brief Keyboard bindings for the viewer controls.
    clear_key: str = "c"
    pause_key: str = "p"


# ---------------------------------------------------------------------------
# NiceGUI server configuration
# ---------------------------------------------------------------------------


@dataclass
class RenderCfg:
    # @brief Browser-rendering controls; raw acquisition windows remain unchanged.

    downsample_enabled: bool = True
    max_points_time_series: int = 1200
    max_points_xy: int = 1500


@dataclass
class ServerCfg:
    # @brief NiceGUI server settings; replaces the PyQt5/Matplotlib window.

    host: str = "127.0.0.1"
    port: int = 8765
    reload: bool = False
    show: bool = True       # auto-open browser on start
    dark: bool = False
    title: str = "LSL Viewer"


# ---------------------------------------------------------------------------
# Viewer / display
# ---------------------------------------------------------------------------

@dataclass
class ViewerCfg:
    # @brief Viewer window, display, and UI settings.
    window_seconds: float = 10.0
    target_window_samples: int = 1600
    reference_window_extra_s: float = 1.0
    expected_target_rate_hz: float = 100.0
    refresh_s: float = 0.05
    force_unit_label: str = "N"
    target_raw_unit_label: str = "count"
    dt_unit_label: str = "ms"
    xy_correlation: XYCorrelationCfg = field(default_factory=XYCorrelationCfg)
    style: StyleCfg = field(default_factory=StyleCfg)
    controls: ControlsCfg = field(default_factory=ControlsCfg)
    render: RenderCfg = field(default_factory=RenderCfg)
    server: ServerCfg = field(default_factory=ServerCfg)


# ---------------------------------------------------------------------------
# Interpolation / alignment policy
# ---------------------------------------------------------------------------

@dataclass
class AlignmentCfg:
    # @brief Interpolation and gap policy for XY alignment.
    interpolation: str = "linear"
    max_reference_gap_s: float = 0.020
    allow_extrapolation: bool = False


# ---------------------------------------------------------------------------
# Calibration marker overlays
# ---------------------------------------------------------------------------

@dataclass
class CalibrationMarkersCfg:
    # @brief Optional calibration-marker overlay configuration.
    enabled: bool = False
    events_ndjson_path: str | None = None
    draw_events: list[str] = field(
        default_factory=lambda: [
            "hold_start",
            "stable_window_start",
            "hold_end",
            "trial_accept",
            "trial_reject",
        ]
    )


# ---------------------------------------------------------------------------
# Replay file paths
# ---------------------------------------------------------------------------

@dataclass
class ReferenceCfg:
    # @brief Replay input paths for CSV and XDF data.
    target_csv_path: str = "./data/target_handgrip_samples_v2.csv"
    reference_csv_path: str = "./data/reference_rs485_samples_v2.csv"
    xdf_path: str | None = None


# ---------------------------------------------------------------------------
# Replay playback settings
# ---------------------------------------------------------------------------

@dataclass
class ReplayCfg:
    # @brief Replay playback controls.
    speed: float = 1.0
    loop: bool = False
    start_offset_s: float = 0.0


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

@dataclass
class LoggingCfg:
    # @brief Logging configuration used by the viewer entry point.
    level: str = "INFO"
    log_file: str = "handgrip_realtime_viewer.log"
    max_bytes: int = 10_485_760   # 10 MB per file
    backup_count: int = 3


# ---------------------------------------------------------------------------
# Root application config
# ---------------------------------------------------------------------------

@dataclass
class AppConfig:
    # @brief Root configuration object registered with Hydra.
    mode: str = "live"
    streams: StreamsCfg = field(default_factory=StreamsCfg)
    channels: ChannelsCfg = field(default_factory=ChannelsCfg)
    viewer: ViewerCfg = field(default_factory=ViewerCfg)
    alignment: AlignmentCfg = field(default_factory=AlignmentCfg)
    calibration_markers: CalibrationMarkersCfg = field(default_factory=CalibrationMarkersCfg)
    reference: ReferenceCfg = field(default_factory=ReferenceCfg)
    replay: ReplayCfg = field(default_factory=ReplayCfg)
    logging: LoggingCfg = field(default_factory=LoggingCfg)


def register_config() -> None:
    # @brief Register the structured config schema with Hydra's ConfigStore.
    ##
    # Must be called before the \@hydra.main decorator is evaluated.
    cs = ConfigStore.instance()
    cs.store(name="app_config", node=AppConfig)
