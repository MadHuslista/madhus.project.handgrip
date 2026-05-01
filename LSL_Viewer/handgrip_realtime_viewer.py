from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import hydra
import matplotlib

matplotlib.use("Qt5Agg")
import numpy as np
import pandas as pd
from hydra.utils import to_absolute_path
from matplotlib import pyplot as plt
from omegaconf import DictConfig, OmegaConf

LOGGER = logging.getLogger("handgrip_realtime_viewer")

RAW_COLOR = "red"
FILTERED_COLOR = "green"
REFERENCE_COLOR = "purple"
TIMING_COLOR = "blue"
GRID_ALPHA = 0.3

ALLOWED_MODES = {"live", "live_with_reference_validation", "csv_replay", "xdf_replay"}


@dataclass(slots=True)
class StreamLayout:
    clock_label: str
    raw_label: str
    filtered_label: str | None = None

    @property
    def picks(self) -> list[str]:
        out = [self.clock_label, self.raw_label]
        if self.filtered_label is not None:
            out.append(self.filtered_label)
        return out


@dataclass(slots=True)
class TargetWindow:
    timestamps_s: np.ndarray
    device_clock_us: np.ndarray
    raw: np.ndarray
    filtered: np.ndarray


@dataclass(slots=True)
class ReferenceWindow:
    timestamps_s: np.ndarray
    rs485_clock: np.ndarray
    raw: np.ndarray


@dataclass(slots=True)
class DualWindow:
    target: TargetWindow | None
    reference: ReferenceWindow | None


@dataclass(slots=True)
class DualReplayData:
    target_timestamps_s: np.ndarray
    target_device_clock_us: np.ndarray
    target_raw: np.ndarray
    target_filtered: np.ndarray
    reference_timestamps_s: np.ndarray
    reference_clock_s: np.ndarray
    reference_raw: np.ndarray
    source_name: str
    source_type: str
    target_labels: list[str]
    reference_labels: list[str]

    @property
    def duration_s(self) -> float:
        values = []
        if self.target_timestamps_s.size:
            values.append(float(np.nanmax(self.target_timestamps_s)))
        if self.reference_timestamps_s.size:
            values.append(float(np.nanmax(self.reference_timestamps_s)))
        return max(values) if values else 0.0


@dataclass(slots=True)
class FigureHandles:
    fig: Any
    axes: dict[str, Any]
    artists: dict[str, Any]
    state: dict[str, Any]


def configure_logging(level_name: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level_name.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,
    )


def _optional_path(value: str | None) -> Path | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return Path(to_absolute_path(text))


def _cfg_str_path(cfg: DictConfig, path: str, default: str) -> str:
    value = OmegaConf.select(cfg, path, default=default)
    return default if value is None else str(value)


def _cfg_bool_path(cfg: DictConfig, path: str, default: bool) -> bool:
    value = OmegaConf.select(cfg, path, default=default)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _force_unit_label(cfg: DictConfig) -> str:
    return str(OmegaConf.select(cfg, "viewer.force_unit_label", default="N"))


def _xy_lock_max_span_enabled(cfg: DictConfig) -> bool:
    return _cfg_bool_path(cfg, "viewer.xy_correlation.lock_max_span", False)


def _xy_lock_toggle_key(cfg: DictConfig) -> str:
    return _cfg_str_path(cfg, "viewer.xy_correlation.toggle_key", "x").strip()


def _clear_plots_key(cfg: DictConfig) -> str:
    return _cfg_str_path(cfg, "viewer.controls.clear_key", "c").strip()


def _pause_live_key(cfg: DictConfig) -> str:
    return _cfg_str_path(cfg, "viewer.controls.pause_key", "p").strip()


def _first_scalar(value: Any):
    if isinstance(value, list) and value:
        return _first_scalar(value[0])
    return value


def _extract_xdf_labels(info: dict[str, Any]) -> list[str] | None:
    desc = info.get("desc", [{}])
    labels: list[str] = []
    if desc and isinstance(desc, list):
        channels_root = desc[0].get("channels", [{}])
        if channels_root and isinstance(channels_root, list):
            channel_items = channels_root[0].get("channel", [])
            for channel in channel_items:
                label = _first_scalar(channel.get("label"))
                if label is not None:
                    labels.append(str(label))
    return labels or None


def target_layout_from_cfg(cfg: DictConfig) -> StreamLayout:
    return StreamLayout(
        clock_label=str(cfg.channels.target.clock_label),
        raw_label=str(cfg.channels.target.raw_label),
        filtered_label=str(cfg.channels.target.filtered_label),
    )


def reference_layout_from_cfg(cfg: DictConfig) -> StreamLayout:
    return StreamLayout(
        clock_label=str(cfg.channels.reference.clock_label),
        raw_label=str(cfg.channels.reference.raw_label),
        filtered_label=None,
    )


def validate_labels(ch_names: list[str], layout: StreamLayout, role: str) -> None:
    missing = [label for label in layout.picks if label not in ch_names]
    if missing:
        raise RuntimeError(f"{role} stream is missing required channels {missing}. Available channels: {ch_names}")


def build_streams(cfg: DictConfig):
    try:
        from mne_lsl.stream import StreamLSL
    except ImportError as exc:
        raise RuntimeError("mne-lsl is required for live streaming. Install it before running live mode.") from exc

    target_cfg = cfg.streams.target
    reference_cfg = cfg.streams.reference

    target = StreamLSL(
        bufsize=int(target_cfg.buffer_samples),
        name=str(target_cfg.name),
        stype=str(target_cfg.stype),
        source_id=None if target_cfg.source_id is None else str(target_cfg.source_id),
    )
    reference = StreamLSL(
        bufsize=float(reference_cfg.buffer_seconds),
        name=str(reference_cfg.name),
        stype=str(reference_cfg.stype),
        source_id=None if reference_cfg.source_id is None else str(reference_cfg.source_id),
    )

    target.connect(acquisition_delay=float(target_cfg.acquisition_delay), timeout=float(target_cfg.timeout))
    reference.connect(acquisition_delay=float(reference_cfg.acquisition_delay), timeout=float(reference_cfg.timeout))

    target_layout = target_layout_from_cfg(cfg)
    reference_layout = reference_layout_from_cfg(cfg)
    validate_labels(list(target.ch_names), target_layout, "Target")
    validate_labels(list(reference.ch_names), reference_layout, "Reference")

    LOGGER.info(
        "Connected target stream: name=%s type=%s source_id=%s sfreq=%s ch_names=%s",
        target.name,
        target.stype,
        target.source_id,
        target.info["sfreq"],
        target.ch_names,
    )
    LOGGER.info(
        "Connected reference stream: name=%s type=%s source_id=%s sfreq=%s ch_names=%s",
        reference.name,
        reference.stype,
        reference.source_id,
        reference.info["sfreq"],
        reference.ch_names,
    )
    if float(target.info["sfreq"]) != 0.0:
        LOGGER.warning("Target stream should normally be irregular (sfreq=0). Current sfreq=%s", target.info["sfreq"])
    if abs(float(reference.info["sfreq"]) - float(reference_cfg.expected_rate_hz)) > 5.0:
        LOGGER.warning(
            "Reference stream sfreq=%s differs from expected_rate_hz=%s.",
            reference.info["sfreq"],
            reference_cfg.expected_rate_hz,
        )
    return target, reference, target_layout, reference_layout


def _stream_data_to_window(data: np.ndarray, ts: np.ndarray, role: str) -> TargetWindow | ReferenceWindow | None:
    if ts.size == 0:
        return None
    timestamps = np.asarray(ts, dtype=np.float64)
    matrix = np.asarray(data, dtype=np.float64)
    if matrix.ndim != 2:
        return None
    if role == "target":
        if matrix.shape[0] < 3:
            return None
        return TargetWindow(
            timestamps_s=timestamps,
            device_clock_us=matrix[0],
            raw=matrix[1],
            filtered=matrix[2],
        )
    if matrix.shape[0] < 2:
        return None
    return ReferenceWindow(
        timestamps_s=timestamps,
        rs485_clock=matrix[0],
        raw=matrix[1],
    )


def fetch_live_window(target_stream, reference_stream, cfg: DictConfig, target_layout: StreamLayout, reference_layout: StreamLayout) -> DualWindow | None:
    target_data, target_ts = target_stream.get_data(
        winsize=int(cfg.viewer.target_window_samples),
        picks=target_layout.picks,
    )
    reference_data, reference_ts = reference_stream.get_data(
        winsize=float(cfg.viewer.window_seconds) + float(cfg.viewer.reference_window_extra_s),
        picks=reference_layout.picks,
    )

    target_window = _stream_data_to_window(target_data, target_ts, "target")
    reference_window = _stream_data_to_window(reference_data, reference_ts, "reference")
    if target_window is None and reference_window is None:
        return None

    # Keep a common visible time interval without forcing a common sample grid.
    latest_values = []
    if target_window is not None and target_window.timestamps_s.size:
        latest_values.append(float(np.nanmax(target_window.timestamps_s)))
    if reference_window is not None and reference_window.timestamps_s.size:
        latest_values.append(float(np.nanmax(reference_window.timestamps_s)))
    if latest_values:
        t_end = max(latest_values)
        t_start = t_end - float(cfg.viewer.window_seconds)
        target_window = _slice_target_window(target_window, t_start) if target_window is not None else None
        reference_window = _slice_reference_window(reference_window, t_start) if reference_window is not None else None
    return DualWindow(target=target_window, reference=reference_window)


def _slice_target_window(window: TargetWindow, t_start: float) -> TargetWindow | None:
    mask = np.asarray(window.timestamps_s) >= float(t_start)
    if not np.any(mask):
        return None
    return TargetWindow(
        timestamps_s=window.timestamps_s[mask],
        device_clock_us=window.device_clock_us[mask],
        raw=window.raw[mask],
        filtered=window.filtered[mask],
    )


def _slice_reference_window(window: ReferenceWindow, t_start: float) -> ReferenceWindow | None:
    mask = np.asarray(window.timestamps_s) >= float(t_start)
    if not np.any(mask):
        return None
    return ReferenceWindow(
        timestamps_s=window.timestamps_s[mask],
        rs485_clock=window.rs485_clock[mask],
        raw=window.raw[mask],
    )


def _slice_dual_after_cutoffs(window: DualWindow, target_cutoff: float | None, reference_cutoff: float | None) -> DualWindow | None:
    target = window.target
    reference = window.reference
    if target is not None and target_cutoff is not None:
        mask = target.timestamps_s > float(target_cutoff)
        target = TargetWindow(target.timestamps_s[mask], target.device_clock_us[mask], target.raw[mask], target.filtered[mask]) if np.any(mask) else None
    if reference is not None and reference_cutoff is not None:
        mask = reference.timestamps_s > float(reference_cutoff)
        reference = ReferenceWindow(reference.timestamps_s[mask], reference.rs485_clock[mask], reference.raw[mask]) if np.any(mask) else None
    if target is None and reference is None:
        return None
    return DualWindow(target=target, reference=reference)


def _establish_live_cutoff_from_latest_window(target_stream, reference_stream, cfg: DictConfig, target_layout: StreamLayout, reference_layout: StreamLayout, handles: FigureHandles) -> None:
    latest = fetch_live_window(target_stream, reference_stream, cfg, target_layout, reference_layout)
    if latest is not None and latest.target is not None and latest.target.timestamps_s.size:
        handles.state["target_live_cutoff_timestamp_s"] = float(np.nanmax(latest.target.timestamps_s))
    else:
        handles.state["target_live_cutoff_timestamp_s"] = None
    if latest is not None and latest.reference is not None and latest.reference.timestamps_s.size:
        handles.state["reference_live_cutoff_timestamp_s"] = float(np.nanmax(latest.reference.timestamps_s))
    else:
        handles.state["reference_live_cutoff_timestamp_s"] = None
    LOGGER.info(
        "Live render cutoffs reset: target=%s reference=%s",
        handles.state["target_live_cutoff_timestamp_s"],
        handles.state["reference_live_cutoff_timestamp_s"],
    )
    handles.state["live_reset_from_latest_window"] = False


def _finite_xy(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mask = np.isfinite(x) & np.isfinite(y)
    return x[mask], y[mask]


def _compute_axis_limits(x: np.ndarray, y: np.ndarray, margin_ratio: float = 0.05) -> tuple[float, float, float, float] | None:
    x, y = _finite_xy(np.asarray(x, dtype=np.float64), np.asarray(y, dtype=np.float64))
    if y.size == 0 or x.size == 0:
        return None
    ymin = float(np.nanmin(y))
    ymax = float(np.nanmax(y))
    if math.isclose(ymin, ymax):
        span = max(1.0, abs(ymin) * 0.05)
        ymin -= span
        ymax += span
    else:
        margin = (ymax - ymin) * margin_ratio
        ymin -= margin
        ymax += margin
    xmin = float(np.nanmin(x))
    xmax = float(np.nanmax(x))
    if math.isclose(xmin, xmax):
        span = max(1.0, abs(xmin) * 0.05)
        xmin -= span
        xmax += span
    else:
        margin = (xmax - xmin) * margin_ratio
        xmin -= margin
        xmax += margin
    return xmin, xmax, ymin, ymax


def update_axis(ax, x: np.ndarray, y: np.ndarray, margin_ratio: float = 0.05) -> None:
    limits = _compute_axis_limits(x, y, margin_ratio=margin_ratio)
    if limits is None:
        return
    xmin, xmax, ymin, ymax = limits
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)


def update_axis_expand_only(ax, x: np.ndarray, y: np.ndarray, state: dict[str, Any], state_key: str, margin_ratio: float = 0.05) -> None:
    limits = _compute_axis_limits(x, y, margin_ratio=margin_ratio)
    if limits is None:
        return
    xmin, xmax, ymin, ymax = limits
    axis_limits = state.setdefault("axis_expand_only_limits", {})
    previous = axis_limits.get(state_key)
    if previous is None:
        locked = {"xmin": xmin, "xmax": xmax, "ymin": ymin, "ymax": ymax}
    else:
        locked = {
            "xmin": min(float(previous["xmin"]), xmin),
            "xmax": max(float(previous["xmax"]), xmax),
            "ymin": min(float(previous["ymin"]), ymin),
            "ymax": max(float(previous["ymax"]), ymax),
        }
    axis_limits[state_key] = locked
    ax.set_xlim(locked["xmin"], locked["xmax"])
    ax.set_ylim(locked["ymin"], locked["ymax"])


def clear_plot_artists(handles: FigureHandles, reset_axes: bool = True) -> None:
    for artist in handles.artists.values():
        if hasattr(artist, "set_data"):
            artist.set_data([], [])
    handles.state.setdefault("axis_expand_only_limits", {}).clear()
    if reset_axes:
        for key, ax in handles.axes.items():
            if key == "info":
                continue
            ax.set_xlim(0.0, 1.0)
            ax.set_ylim(-1.0, 1.0)
    if hasattr(handles.fig, "canvas"):
        handles.fig.canvas.draw_idle()


def _clock_interval_ms(clock_values: np.ndarray, scale_to_ms: float) -> tuple[np.ndarray, np.ndarray, float, float]:
    values = np.asarray(clock_values, dtype=np.float64)
    finite = np.isfinite(values)
    if np.count_nonzero(finite) < 2:
        return np.array([], dtype=np.int64), np.array([], dtype=np.float64), float("nan"), float("nan")
    idx = np.flatnonzero(finite)
    diffs = np.diff(values[idx]) * scale_to_ms
    valid = np.isfinite(diffs) & (diffs > 0)
    if not np.any(valid):
        return np.array([], dtype=np.int64), np.array([], dtype=np.float64), float("nan"), float("nan")
    out_idx = idx[1:][valid]
    out_dt = diffs[valid]
    mean_dt_ms = float(np.nanmean(out_dt))
    rate_hz = 1000.0 / mean_dt_ms if mean_dt_ms > 0 else float("nan")
    return out_idx, out_dt, rate_hz, mean_dt_ms


def _lsl_interval_ms(timestamps_s: np.ndarray) -> tuple[np.ndarray, np.ndarray, float, float]:
    ts = np.asarray(timestamps_s, dtype=np.float64)
    finite = np.isfinite(ts)
    if np.count_nonzero(finite) < 2:
        return np.array([], dtype=np.int64), np.array([], dtype=np.float64), float("nan"), float("nan")
    idx = np.flatnonzero(finite)
    diffs_ms = np.diff(ts[idx]) * 1000.0
    valid = np.isfinite(diffs_ms) & (diffs_ms > 0)
    if not np.any(valid):
        return np.array([], dtype=np.int64), np.array([], dtype=np.float64), float("nan"), float("nan")
    out_idx = idx[1:][valid]
    out_dt = diffs_ms[valid]
    mean_dt_ms = float(np.nanmean(out_dt))
    rate_hz = 1000.0 / mean_dt_ms if mean_dt_ms > 0 else float("nan")
    return out_idx, out_dt, rate_hz, mean_dt_ms


def _interpolate_reference_to_target(target: TargetWindow | None, reference: ReferenceWindow | None, max_reference_gap_s: float) -> tuple[np.ndarray, np.ndarray]:
    if target is None or reference is None:
        return np.array([], dtype=np.float64), np.array([], dtype=np.float64)
    if target.timestamps_s.size == 0 or reference.timestamps_s.size < 2:
        return np.array([], dtype=np.float64), np.array([], dtype=np.float64)

    ref_t = np.asarray(reference.timestamps_s, dtype=np.float64)
    ref_y = np.asarray(reference.raw, dtype=np.float64)
    target_t = np.asarray(target.timestamps_s, dtype=np.float64)
    target_y = np.asarray(target.raw, dtype=np.float64)

    order = np.argsort(ref_t)
    ref_t = ref_t[order]
    ref_y = ref_y[order]
    unique_mask = np.concatenate([[True], np.diff(ref_t) > 0])
    ref_t = ref_t[unique_mask]
    ref_y = ref_y[unique_mask]
    if ref_t.size < 2:
        return np.array([], dtype=np.float64), np.array([], dtype=np.float64)

    inside = (target_t >= ref_t[0]) & (target_t <= ref_t[-1]) & np.isfinite(target_y)
    if not np.any(inside):
        return np.array([], dtype=np.float64), np.array([], dtype=np.float64)

    nearest_right = np.searchsorted(ref_t, target_t[inside], side="left")
    nearest_right = np.clip(nearest_right, 0, ref_t.size - 1)
    nearest_left = np.clip(nearest_right - 1, 0, ref_t.size - 1)
    nearest_gap = np.minimum(np.abs(target_t[inside] - ref_t[nearest_left]), np.abs(ref_t[nearest_right] - target_t[inside]))
    valid_gap = nearest_gap <= float(max_reference_gap_s)
    if not np.any(valid_gap):
        return np.array([], dtype=np.float64), np.array([], dtype=np.float64)

    selected_t = target_t[inside][valid_gap]
    selected_target_y = target_y[inside][valid_gap]
    ref_at_target = np.interp(selected_t, ref_t, ref_y)
    return selected_target_y, ref_at_target


def _format_latest(value: float, suffix: str = "", precision: int = 3) -> str:
    if not np.isfinite(value):
        return "nan"
    return f"{value:.{precision}f}{suffix}"


def _zip_columns(*columns: str, pad: int = 3) -> str:
    split_cols = [col.splitlines() for col in columns]
    widths = [max((len(line) for line in lines), default=0) for lines in split_cols]
    height = max((len(lines) for lines in split_cols), default=0)
    rows: list[str] = []
    for row_idx in range(height):
        row_parts = []
        for lines, width in zip(split_cols, widths):
            text = lines[row_idx] if row_idx < len(lines) else ""
            row_parts.append(text.ljust(width + pad))
        rows.append("".join(row_parts).rstrip())
    return "\n".join(rows)


def init_figure(cfg: DictConfig) -> FigureHandles:
    fig = plt.figure(figsize=(16, 10))
    gs = fig.add_gridspec(4, 2, height_ratios=[1.0, 1.2, 1.2, 1.2])
    axes = {
        "info": fig.add_subplot(gs[0, :]),
        "target_raw": fig.add_subplot(gs[1, 0]),
        "target_filtered": fig.add_subplot(gs[2, 0]),
        "target_dt": fig.add_subplot(gs[3, 0]),
        "reference_raw": fig.add_subplot(gs[1, 1]),
        "overlay": fig.add_subplot(gs[2, 1]),
        "reference_dt": fig.add_subplot(gs[3, 1]),
    }
    # Twin the overlay axis for XY as a separate floating figure-like axis? Keep
    # one extra inset-style axis by using a secondary y panel title. Simpler and
    # more readable: create XY in a new axes over the info panel's right side.
    xy_ax = axes["info"].inset_axes([0.70, 0.05, 0.28, 0.85])
    axes["xy"] = xy_ax

    artists: dict[str, Any] = {}
    axes["info"].axis("off")
    artists["target_raw"], = axes["target_raw"].plot([], [], color=RAW_COLOR, lw=1.0, label="target raw")
    artists["target_filtered"], = axes["target_filtered"].plot([], [], color=FILTERED_COLOR, lw=1.0, label="target filtered")
    artists["target_dt"], = axes["target_dt"].plot([], [], color=TIMING_COLOR, lw=1.0, label="target dt")
    artists["reference_raw"], = axes["reference_raw"].plot([], [], color=REFERENCE_COLOR, lw=1.0, label="reference raw")
    artists["overlay_target"], = axes["overlay"].plot([], [], color=RAW_COLOR, lw=1.0, label="target raw")
    artists["overlay_reference"], = axes["overlay"].plot([], [], color=REFERENCE_COLOR, lw=1.0, label="reference raw")
    artists["reference_dt"], = axes["reference_dt"].plot([], [], color=TIMING_COLOR, lw=1.0, label="reference dt")
    artists["xy"], = axes["xy"].plot([], [], color="black", lw=0.8, marker=".", ms=2, linestyle="none", label="target vs ref@target")

    force_unit = _force_unit_label(cfg)
    axes["target_raw"].set_title("Target raw - native samples")
    axes["target_raw"].set_ylabel(force_unit)
    axes["target_filtered"].set_title("Target filtered - native samples")
    axes["target_filtered"].set_ylabel(force_unit)
    axes["target_dt"].set_title("Target LSL sample interval")
    axes["target_dt"].set_xlabel("time relative to latest sample (s)")
    axes["target_dt"].set_ylabel("dt (ms)")
    axes["reference_raw"].set_title("Reference RS485 raw - native 500 Hz samples")
    axes["reference_raw"].set_ylabel(force_unit)
    axes["overlay"].set_title("Overlay on common LSL time axis")
    axes["overlay"].set_ylabel(force_unit)
    axes["reference_dt"].set_title("Reference LSL sample interval")
    axes["reference_dt"].set_xlabel("time relative to latest sample (s)")
    axes["reference_dt"].set_ylabel("dt (ms)")
    axes["xy"].set_title("XY: target raw vs reference interpolated to target timestamps", fontsize=8)
    axes["xy"].set_xlabel("target raw", fontsize=8)
    axes["xy"].set_ylabel("reference", fontsize=8)

    for key, ax in axes.items():
        if key == "info":
            continue
        ax.grid(True, alpha=GRID_ALPHA)
        if key != "xy":
            ax.legend(loc="upper right", fontsize=8)

    state = {
        "axis_expand_only_limits": {},
        "xy_lock_max_span": _xy_lock_max_span_enabled(cfg),
        "xy_lock_toggle_key": _xy_lock_toggle_key(cfg),
        "clear_plots_key": _clear_plots_key(cfg),
        "pause_live_key": _pause_live_key(cfg),
        "live_paused": False,
        "live_reset_from_latest_window": False,
        "target_live_cutoff_timestamp_s": None,
        "reference_live_cutoff_timestamp_s": None,
    }
    handles = FigureHandles(fig=fig, axes=axes, artists=artists, state=state)

    def on_key(event: Any) -> None:
        if event.key is None:
            return
        if event.key == state.get("xy_lock_toggle_key"):
            state["xy_lock_max_span"] = not bool(state.get("xy_lock_max_span", False))
            state.setdefault("axis_expand_only_limits", {}).pop("xy", None)
            LOGGER.info("XY max-span lock toggled: %s", state["xy_lock_max_span"])
        elif event.key == state.get("clear_plots_key"):
            clear_plot_artists(handles)
            state["live_reset_from_latest_window"] = True
            LOGGER.info("Manual plot clear requested; buffered samples will be dropped on next live update.")
        elif event.key == state.get("pause_live_key"):
            state["live_paused"] = not bool(state.get("live_paused", False))
            if not state["live_paused"]:
                clear_plot_artists(handles)
                state["live_reset_from_latest_window"] = True
            LOGGER.info("Live pause toggled: %s", state["live_paused"])

    fig.canvas.mpl_connect("key_press_event", on_key)
    fig.tight_layout()
    return handles


def _render_info_panel(handles: FigureHandles, text: str) -> None:
    ax = handles.axes["info"]
    # Preserve XY inset; clear only text artists previously added to the main info axis.
    for artist in list(ax.texts):
        artist.remove()
    ax.axis("off")
    ax.text(0.02, 0.94, text, va="top", ha="left", family="monospace", fontsize=8, transform=ax.transAxes)


def update_plots(handles: FigureHandles, window: DualWindow, cfg: DictConfig, *, mode: str, source_name: str, source_type: str, target_new_samples: int | None = None, reference_new_samples: int | None = None, replay_progress_text: str | None = None) -> None:
    target = window.target
    reference = window.reference
    latest_ts_candidates = []
    if target is not None and target.timestamps_s.size:
        latest_ts_candidates.append(float(np.nanmax(target.timestamps_s)))
    if reference is not None and reference.timestamps_s.size:
        latest_ts_candidates.append(float(np.nanmax(reference.timestamps_s)))
    t_end = max(latest_ts_candidates) if latest_ts_candidates else 0.0
    force_unit = _force_unit_label(cfg)

    target_rate_hz = float("nan")
    target_mean_dt_ms = float("nan")
    if target is not None and target.timestamps_s.size:
        target_t_rel = target.timestamps_s - t_end
        handles.artists["target_raw"].set_data(target_t_rel, target.raw)
        handles.artists["target_filtered"].set_data(target_t_rel, target.filtered)
        handles.artists["overlay_target"].set_data(target_t_rel, target.raw)
        update_axis(handles.axes["target_raw"], target_t_rel, target.raw)
        update_axis(handles.axes["target_filtered"], target_t_rel, target.filtered)
        target_dt_indices, target_dt_ms, target_rate_hz, target_mean_dt_ms = _lsl_interval_ms(target.timestamps_s)
        if target_dt_ms.size:
            handles.artists["target_dt"].set_data(target_t_rel[target_dt_indices.astype(int)], target_dt_ms)
            update_axis(handles.axes["target_dt"], target_t_rel[target_dt_indices.astype(int)], target_dt_ms)
    else:
        handles.artists["target_raw"].set_data([], [])
        handles.artists["target_filtered"].set_data([], [])
        handles.artists["overlay_target"].set_data([], [])
        handles.artists["target_dt"].set_data([], [])

    reference_rate_hz = float("nan")
    reference_mean_dt_ms = float("nan")
    if reference is not None and reference.timestamps_s.size:
        ref_t_rel = reference.timestamps_s - t_end
        handles.artists["reference_raw"].set_data(ref_t_rel, reference.raw)
        handles.artists["overlay_reference"].set_data(ref_t_rel, reference.raw)
        update_axis(handles.axes["reference_raw"], ref_t_rel, reference.raw)
        reference_dt_indices, reference_dt_ms, reference_rate_hz, reference_mean_dt_ms = _lsl_interval_ms(reference.timestamps_s)
        if reference_dt_ms.size:
            handles.artists["reference_dt"].set_data(ref_t_rel[reference_dt_indices.astype(int)], reference_dt_ms)
            update_axis(handles.axes["reference_dt"], ref_t_rel[reference_dt_indices.astype(int)], reference_dt_ms)
    else:
        handles.artists["reference_raw"].set_data([], [])
        handles.artists["overlay_reference"].set_data([], [])
        handles.artists["reference_dt"].set_data([], [])

    overlay_x: list[np.ndarray] = []
    overlay_y: list[np.ndarray] = []
    if target is not None and target.timestamps_s.size:
        target_t_rel = target.timestamps_s - t_end
        overlay_x.append(target_t_rel[np.isfinite(target_t_rel)])
        overlay_y.append(target.raw[np.isfinite(target_t_rel) & np.isfinite(target.raw)])
    if reference is not None and reference.timestamps_s.size:
        ref_t_rel = reference.timestamps_s - t_end
        overlay_x.append(ref_t_rel[np.isfinite(ref_t_rel)])
        overlay_y.append(reference.raw[np.isfinite(ref_t_rel) & np.isfinite(reference.raw)])
    if overlay_x and overlay_y:
        x = np.concatenate(overlay_x)
        y = np.concatenate(overlay_y)
        update_axis(handles.axes["overlay"], x, y)

    xy_x, xy_y = _interpolate_reference_to_target(
        target,
        reference,
        max_reference_gap_s=float(cfg.alignment.max_reference_gap_s),
    )
    handles.artists["xy"].set_data(xy_x, xy_y)
    xy_lock_max_span = bool(handles.state.get("xy_lock_max_span", False))
    xy_mode = "max-span lock" if xy_lock_max_span else "adaptive"
    handles.axes["xy"].set_title(f"XY: target raw vs reference@target [{xy_mode}]", fontsize=8)
    if xy_x.size:
        if xy_lock_max_span:
            update_axis_expand_only(handles.axes["xy"], xy_x, xy_y, handles.state, "xy")
        else:
            handles.state.setdefault("axis_expand_only_limits", {}).pop("xy", None)
            update_axis(handles.axes["xy"], xy_x, xy_y)

    live_state = "paused" if bool(handles.state.get("live_paused", False)) else "running"
    latest_target_raw = float(target.raw[-1]) if target is not None and target.raw.size else float("nan")
    latest_target_filtered = float(target.filtered[-1]) if target is not None and target.filtered.size else float("nan")
    latest_target_clock = float(target.device_clock_us[-1]) if target is not None and target.device_clock_us.size else float("nan")
    latest_reference_raw = float(reference.raw[-1]) if reference is not None and reference.raw.size else float("nan")
    latest_reference_clock = float(reference.rs485_clock[-1]) if reference is not None and reference.rs485_clock.size else float("nan")

    col_source = (
        "SOURCE/MODE\n"
        f"source : {source_name}\n"
        f"type   : {source_type}\n"
        f"mode   : {mode}\n"
        f"state  : {live_state}\n"
        "sync   : native streams + LSL timestamps"
    )
    col_target = (
        f"TARGET ({force_unit})\n"
        f"raw    : {_format_latest(latest_target_raw)}\n"
        f"filt   : {_format_latest(latest_target_filtered)}\n"
        f"clock  : {_format_latest(latest_target_clock, ' us', 0)}\n"
        f"rate   : {_format_latest(target_rate_hz, ' Hz', 2)}\n"
        f"dt     : {_format_latest(target_mean_dt_ms, ' ms', 2)}"
    )
    col_reference = (
        f"REFERENCE ({force_unit})\n"
        f"raw    : {_format_latest(latest_reference_raw)}\n"
        f"clock  : {_format_latest(latest_reference_clock, ' s', 6)}\n"
        f"rate   : {_format_latest(reference_rate_hz, ' Hz', 2)}\n"
        f"dt     : {_format_latest(reference_mean_dt_ms, ' ms', 2)}\n"
        f"pairs  : {xy_x.size}"
    )
    col_metrics = "METRICS\n"
    if target_new_samples is not None or reference_new_samples is not None:
        col_metrics += f"new tgt: {target_new_samples}\nnew ref: {reference_new_samples}\n"
    elif replay_progress_text:
        col_metrics += replay_progress_text + "\n"
    col_metrics += (
        f"window : {float(cfg.viewer.window_seconds):.1f} s\n"
        f"keys   : clean={handles.state.get('clear_plots_key') or 'off'} "
        f"pause={handles.state.get('pause_live_key') or 'off'} "
        f"xy={handles.state.get('xy_lock_toggle_key') or 'off'}"
    )
    _render_info_panel(handles, _zip_columns(col_source, col_target, col_reference, col_metrics))
    handles.fig.canvas.draw_idle()


def _normalize_common_timebases(target_ts: np.ndarray, reference_ts: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    starts = []
    if target_ts.size:
        starts.append(float(target_ts[0]))
    if reference_ts.size:
        starts.append(float(reference_ts[0]))
    t0 = min(starts) if starts else 0.0
    return target_ts - t0, reference_ts - t0


def _candidate_columns(preferred: str, fallbacks: list[str]) -> list[str]:
    seen = []
    for col in [preferred, *fallbacks]:
        if col not in seen:
            seen.append(col)
    return seen


def _pick_existing_column(columns: list[str], candidates: list[str], role: str) -> str:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    raise RuntimeError(f"Could not find a column for {role}. Candidates={candidates}; available={columns}")


def _extract_numeric(df: pd.DataFrame, col: str) -> np.ndarray:
    return pd.to_numeric(df[col], errors="coerce").to_numpy(dtype=np.float64)


def _time_from_df(df: pd.DataFrame, preferred: list[str], expected_rate_hz: float) -> np.ndarray:
    cols = list(df.columns)
    for col in preferred:
        if col in cols:
            values = _extract_numeric(df, col)
            if col.endswith("_ns"):
                return values * 1e-9
            if col.endswith("_us"):
                return values * 1e-6
            return values
    return np.arange(len(df), dtype=np.float64) / float(expected_rate_hz)


def load_csv_replay(cfg: DictConfig) -> DualReplayData:
    target_path = _optional_path(OmegaConf.select(cfg, "reference.target_csv_path", default=None))
    reference_path = _optional_path(OmegaConf.select(cfg, "reference.reference_csv_path", default=None))
    legacy_path = _optional_path(OmegaConf.select(cfg, "reference.csv_path", default=None))

    if target_path is not None and reference_path is not None:
        target_df = pd.read_csv(target_path)
        reference_df = pd.read_csv(reference_path)
        if target_df.empty or reference_df.empty:
            raise RuntimeError("CSV replay source is empty")
        target_cols = list(target_df.columns)
        reference_cols = list(reference_df.columns)
        target_clock = _pick_existing_column(target_cols, _candidate_columns(str(cfg.channels.target.clock_label), ["device_clock_us", "clock_us"]), "target clock")
        target_raw = _pick_existing_column(target_cols, _candidate_columns(str(cfg.channels.target.raw_label), ["value_raw", "raw", "raw_value"]), "target raw")
        target_filtered = _pick_existing_column(target_cols, _candidate_columns(str(cfg.channels.target.filtered_label), ["value_filtered", "filtered", "filtered_value"]), "target filtered")
        ref_clock = _pick_existing_column(reference_cols, _candidate_columns(str(cfg.channels.reference.clock_label), ["reference_clock_s", "rs485_time_s"]), "reference clock")
        ref_raw = _pick_existing_column(reference_cols, _candidate_columns(str(cfg.channels.reference.raw_label), ["reference_raw", "rs485_value"]), "reference raw")
        target_ts = _time_from_df(target_df, ["lsl_timestamp_s", "timestamp_s", "host_lsl_ts"], float(cfg.viewer.expected_target_rate_hz))
        reference_ts = _time_from_df(reference_df, ["lsl_timestamp_s", "host_lsl_ts", "received_lsl_ts"], float(cfg.streams.reference.expected_rate_hz))
        target_ts, reference_ts = _normalize_common_timebases(target_ts, reference_ts)
        return DualReplayData(
            target_timestamps_s=target_ts,
            target_device_clock_us=_extract_numeric(target_df, target_clock),
            target_raw=_extract_numeric(target_df, target_raw),
            target_filtered=_extract_numeric(target_df, target_filtered),
            reference_timestamps_s=reference_ts,
            reference_clock_s=_extract_numeric(reference_df, ref_clock),
            reference_raw=_extract_numeric(reference_df, ref_raw),
            source_name=f"{target_path.name} + {reference_path.name}",
            source_type="csv_replay_dual_native",
            target_labels=[target_clock, target_raw, target_filtered],
            reference_labels=[ref_clock, ref_raw],
        )

    if legacy_path is None:
        raise RuntimeError("mode=csv_replay requires reference.target_csv_path + reference.reference_csv_path, or legacy reference.csv_path")

    # Legacy fused CSV compatibility path.
    df = pd.read_csv(legacy_path)
    if df.empty:
        raise RuntimeError(f"CSV replay source is empty: {legacy_path}")
    cols = list(df.columns)
    target_clock = _pick_existing_column(cols, ["device_clock_us", str(cfg.channels.target.clock_label)], "target clock")
    target_raw = _pick_existing_column(cols, ["value_raw", str(cfg.channels.target.raw_label), "raw"], "target raw")
    target_filtered = _pick_existing_column(cols, ["value_filtered", str(cfg.channels.target.filtered_label), "filtered"], "target filtered")
    ref_clock = _pick_existing_column(cols, ["rs485_clock", str(cfg.channels.reference.clock_label)], "reference clock")
    ref_raw = _pick_existing_column(cols, ["rs485_raw", str(cfg.channels.reference.raw_label)], "reference raw")
    ts = _time_from_df(df, ["lsl_timestamp_s", "host_lsl_ts", "device_clock_us"], float(cfg.viewer.expected_target_rate_hz))
    ts = ts - float(ts[0])
    return DualReplayData(
        target_timestamps_s=ts,
        target_device_clock_us=_extract_numeric(df, target_clock),
        target_raw=_extract_numeric(df, target_raw),
        target_filtered=_extract_numeric(df, target_filtered),
        reference_timestamps_s=ts,
        reference_clock_s=_extract_numeric(df, ref_clock),
        reference_raw=_extract_numeric(df, ref_raw),
        source_name=legacy_path.name,
        source_type="csv_replay_legacy_fused",
        target_labels=[target_clock, target_raw, target_filtered],
        reference_labels=[ref_clock, ref_raw],
    )


def _select_xdf_stream(streams: list[dict[str, Any]], name: str, stype: str, source_id: str | None) -> dict[str, Any]:
    matches = []
    for stream in streams:
        info = stream.get("info", {})
        s_name = _first_scalar(info.get("name"))
        s_type = _first_scalar(info.get("type"))
        s_source_id = _first_scalar(info.get("source_id"))
        if s_name != name:
            continue
        if s_type != stype:
            continue
        if source_id is not None and s_source_id != source_id:
            continue
        matches.append(stream)
    if not matches:
        raise RuntimeError(f"No XDF stream matched name={name!r} stype={stype!r} source_id={source_id!r}")
    if len(matches) > 1:
        LOGGER.warning("Multiple XDF streams matched for %s; using the first one.", name)
    return matches[0]


def _extract_xdf_time_series(stream: dict[str, Any]) -> np.ndarray:
    ts = np.asarray(stream.get("time_series"), dtype=np.float64)
    if ts.ndim == 1:
        ts = ts[:, np.newaxis]
    if ts.ndim != 2:
        raise RuntimeError(f"Unsupported XDF time_series shape: {ts.shape}")
    return ts


def _extract_xdf_timestamps(stream: dict[str, Any]) -> np.ndarray:
    stamps = np.asarray(stream.get("time_stamps"), dtype=np.float64).reshape(-1)
    if stamps.size == 0:
        raise RuntimeError("XDF stream contains no timestamps")
    if stamps.size >= 2 and np.any(np.diff(stamps) < 0):
        raise RuntimeError("XDF timestamps are not monotonic increasing")
    return stamps


def _indices_from_labels(labels: list[str], required: list[str], role: str) -> list[int]:
    indices = []
    for label in required:
        if label not in labels:
            raise RuntimeError(f"{role} XDF stream labels do not contain {label!r}. labels={labels}")
        indices.append(labels.index(label))
    return indices


def load_xdf_replay(cfg: DictConfig) -> DualReplayData:
    xdf_path = _optional_path(cfg.reference.xdf_path)
    if xdf_path is None:
        raise RuntimeError("mode=xdf_replay requires reference.xdf_path")
    try:
        import pyxdf  # type: ignore
    except ImportError as exc:
        raise RuntimeError("mode=xdf_replay requires pyxdf. Install it before using XDF replay.") from exc

    streams, header = pyxdf.load_xdf(str(xdf_path), dejitter_timestamps=False)
    LOGGER.info("XDF replay loaded: %s | file header keys=%s | streams=%d", xdf_path, list(header.keys()), len(streams))
    target_stream = _select_xdf_stream(
        streams,
        str(cfg.streams.target.name),
        str(cfg.streams.target.stype),
        None if cfg.streams.target.source_id is None else str(cfg.streams.target.source_id),
    )
    reference_stream = _select_xdf_stream(
        streams,
        str(cfg.streams.reference.name),
        str(cfg.streams.reference.stype),
        None if cfg.streams.reference.source_id is None else str(cfg.streams.reference.source_id),
    )

    target_labels = _extract_xdf_labels(target_stream.get("info", {})) or [str(cfg.channels.target.clock_label), str(cfg.channels.target.raw_label), str(cfg.channels.target.filtered_label)]
    reference_labels = _extract_xdf_labels(reference_stream.get("info", {})) or [str(cfg.channels.reference.clock_label), str(cfg.channels.reference.raw_label)]
    target_matrix = _extract_xdf_time_series(target_stream)
    reference_matrix = _extract_xdf_time_series(reference_stream)
    target_ts = _extract_xdf_timestamps(target_stream)
    reference_ts = _extract_xdf_timestamps(reference_stream)
    target_ts, reference_ts = _normalize_common_timebases(target_ts, reference_ts)

    target_idx = _indices_from_labels(target_labels, [str(cfg.channels.target.clock_label), str(cfg.channels.target.raw_label), str(cfg.channels.target.filtered_label)], "Target")
    reference_idx = _indices_from_labels(reference_labels, [str(cfg.channels.reference.clock_label), str(cfg.channels.reference.raw_label)], "Reference")

    return DualReplayData(
        target_timestamps_s=target_ts,
        target_device_clock_us=target_matrix[:, target_idx[0]],
        target_raw=target_matrix[:, target_idx[1]],
        target_filtered=target_matrix[:, target_idx[2]],
        reference_timestamps_s=reference_ts,
        reference_clock_s=reference_matrix[:, reference_idx[0]],
        reference_raw=reference_matrix[:, reference_idx[1]],
        source_name=xdf_path.name,
        source_type="xdf_replay_dual_native",
        target_labels=[target_labels[i] for i in target_idx],
        reference_labels=[reference_labels[i] for i in reference_idx],
    )


def _window_from_replay(data: DualReplayData, elapsed_s: float, window_seconds: float) -> DualWindow | None:
    start_s = max(0.0, float(elapsed_s) - float(window_seconds))
    target_mask = (data.target_timestamps_s >= start_s) & (data.target_timestamps_s <= elapsed_s)
    reference_mask = (data.reference_timestamps_s >= start_s) & (data.reference_timestamps_s <= elapsed_s)
    target = None
    reference = None
    if np.any(target_mask):
        target = TargetWindow(
            timestamps_s=data.target_timestamps_s[target_mask],
            device_clock_us=data.target_device_clock_us[target_mask],
            raw=data.target_raw[target_mask],
            filtered=data.target_filtered[target_mask],
        )
    if np.any(reference_mask):
        reference = ReferenceWindow(
            timestamps_s=data.reference_timestamps_s[reference_mask],
            rs485_clock=data.reference_clock_s[reference_mask],
            raw=data.reference_raw[reference_mask],
        )
    if target is None and reference is None:
        return None
    return DualWindow(target=target, reference=reference)


def run_live_mode(cfg: DictConfig, validate_reference: bool) -> int:
    target_stream, reference_stream, target_layout, reference_layout = build_streams(cfg)
    handles = init_figure(cfg)
    LOGGER.info(
        "Live viewer started: mode=%s target=%s reference=%s window_seconds=%.3f refresh_s=%.3f",
        "live_with_reference_validation" if validate_reference else "live",
        cfg.streams.target.name,
        cfg.streams.reference.name,
        float(cfg.viewer.window_seconds),
        float(cfg.viewer.refresh_s),
    )
    try:
        while plt.fignum_exists(handles.fig.number):
            if bool(handles.state.get("live_paused", False)):
                plt.pause(float(cfg.viewer.refresh_s))
                continue
            if bool(handles.state.get("live_reset_from_latest_window", False)):
                _establish_live_cutoff_from_latest_window(target_stream, reference_stream, cfg, target_layout, reference_layout, handles)
                plt.pause(float(cfg.viewer.refresh_s))
                continue
            live = fetch_live_window(target_stream, reference_stream, cfg, target_layout, reference_layout)
            if live is None:
                plt.pause(float(cfg.viewer.refresh_s))
                continue
            live = _slice_dual_after_cutoffs(
                live,
                handles.state.get("target_live_cutoff_timestamp_s"),
                handles.state.get("reference_live_cutoff_timestamp_s"),
            )
            if live is None:
                plt.pause(float(cfg.viewer.refresh_s))
                continue
            update_plots(
                handles,
                live,
                cfg,
                source_name=f"{target_stream.name} + {reference_stream.name}",
                source_type="dual_native_lsl",
                mode="live_ref" if validate_reference else "live",
                target_new_samples=int(target_stream.n_new_samples),
                reference_new_samples=int(reference_stream.n_new_samples),
            )
            plt.pause(float(cfg.viewer.refresh_s))
    except KeyboardInterrupt:
        LOGGER.info("Stopping on user request")
    finally:
        target_stream.disconnect()
        reference_stream.disconnect()
        plt.close(handles.fig)
    return 0


def run_replay_mode(cfg: DictConfig, replay_data: DualReplayData, mode: str) -> int:
    handles = init_figure(cfg)
    duration_s = replay_data.duration_s
    if duration_s <= 0:
        raise RuntimeError(f"Replay dataset is empty for mode={mode}")
    start_offset_s = max(0.0, float(cfg.replay.start_offset_s))
    replay_speed = max(1e-9, float(cfg.replay.speed))
    loop = bool(cfg.replay.loop)
    LOGGER.info(
        "Replay viewer started: mode=%s source=%s type=%s duration=%.3fs refresh_s=%.3f speed=%.3f loop=%s",
        mode,
        replay_data.source_name,
        replay_data.source_type,
        duration_s,
        float(cfg.viewer.refresh_s),
        replay_speed,
        loop,
    )
    replay_start_wall = time.monotonic()
    try:
        while plt.fignum_exists(handles.fig.number):
            elapsed_s = (time.monotonic() - replay_start_wall) * replay_speed + start_offset_s
            if loop and duration_s > 0:
                elapsed_s = elapsed_s % duration_s
            elif elapsed_s > duration_s:
                elapsed_s = duration_s
            window = _window_from_replay(replay_data, elapsed_s, float(cfg.viewer.window_seconds))
            if window is not None:
                progress = f"time   : {elapsed_s:.2f}/{duration_s:.2f} s\nspeed  : {replay_speed:.2f}x"
                update_plots(
                    handles,
                    window,
                    cfg,
                    source_name=replay_data.source_name,
                    source_type=replay_data.source_type,
                    mode=mode,
                    replay_progress_text=progress,
                )
            plt.pause(float(cfg.viewer.refresh_s))
            if elapsed_s >= duration_s and not loop:
                LOGGER.info("Replay reached the end of the dataset; holding final frame.")
                while plt.fignum_exists(handles.fig.number):
                    plt.pause(float(cfg.viewer.refresh_s))
                break
    except KeyboardInterrupt:
        LOGGER.info("Stopping on user request")
    finally:
        plt.close(handles.fig)
    return 0


@hydra.main(version_base=None, config_path="conf", config_name="config")
def app(cfg: DictConfig) -> int:
    configure_logging(str(cfg.logging.level))
    LOGGER.info("Starting dual-native-stream viewer with config:\n%s", OmegaConf.to_yaml(cfg, resolve=True))
    mode = str(cfg.mode)
    if mode not in ALLOWED_MODES:
        raise RuntimeError(f"Unsupported mode={mode!r}. Allowed modes: {sorted(ALLOWED_MODES)}")
    if mode == "live":
        return run_live_mode(cfg, validate_reference=False)
    if mode == "live_with_reference_validation":
        return run_live_mode(cfg, validate_reference=True)
    if mode == "csv_replay":
        return run_replay_mode(cfg, load_csv_replay(cfg), mode)
    if mode == "xdf_replay":
        return run_replay_mode(cfg, load_xdf_replay(cfg), mode)
    raise AssertionError("Unreachable mode dispatch")


if __name__ == "__main__":
    raise SystemExit(app())
