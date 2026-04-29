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
from matplotlib import colors as mcolors
from matplotlib import pyplot as plt
from omegaconf import DictConfig, OmegaConf

LOGGER = logging.getLogger("handgrip_realtime_viewer")

RAW_COLOR = "red"
FILTERED_COLOR = "green"
TIMING_COLOR = "blue"
GRID_ALPHA = 0.3


@dataclass(slots=True)
class OfflineReference:
    csv_columns: list[str] | None = None
    csv_path: Path | None = None
    xdf_labels: list[str] | None = None
    xdf_path: Path | None = None


@dataclass(slots=True, frozen=True)
class ChannelLayout:
    clock_label: str
    raw_label: str
    filtered_label: str
    rs485_raw_label: str
    rs485_clock_label: str
    has_rs485: bool

    @property
    def live_picks(self) -> list[str]:
        picks = [self.clock_label, self.raw_label, self.filtered_label]
        if self.has_rs485:
            picks.extend([self.rs485_raw_label, self.rs485_clock_label])
        return picks

    @property
    def schema_name(self) -> str:
        return "unified_5ch" if self.has_rs485 else "legacy_3ch"


@dataclass(slots=True)
class LiveWindow:
    timestamps_s: np.ndarray
    device_clock_us: np.ndarray
    raw: np.ndarray
    filtered: np.ndarray
    rs485_raw: np.ndarray | None = None
    rs485_clock: np.ndarray | None = None

    @property
    def has_rs485(self) -> bool:
        return self.rs485_raw is not None and self.rs485_clock is not None


@dataclass(slots=True)
class ReplayData:
    timestamps_s: np.ndarray
    device_clock_us: np.ndarray
    raw: np.ndarray
    filtered: np.ndarray
    source_name: str
    source_type: str | None = None
    source_id: str | None = None
    labels: list[str] | None = None
    rs485_raw: np.ndarray | None = None
    rs485_clock: np.ndarray | None = None

    @property
    def has_rs485(self) -> bool:
        return self.rs485_raw is not None and self.rs485_clock is not None

    @property
    def schema_name(self) -> str:
        return "unified_5ch" if self.has_rs485 else "legacy_3ch"


@dataclass(slots=True)
class FigureHandles:
    fig: Any
    axes: dict[str, Any]
    artists: dict[str, Any]


ALLOWED_MODES = {
    "live",
    "live_with_reference_validation",
    "csv_replay",
    "xdf_replay",
}


def configure_logging(level_name: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level_name.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,
    )


def infer_window_samples(cfg: DictConfig) -> int:
    window_samples = cfg.viewer.window_samples
    if window_samples is not None:
        return max(2, int(window_samples))
    return max(2, int(math.ceil(float(cfg.viewer.window_seconds) * float(cfg.viewer.expected_rate_hz))))


def _optional_path(value: str | None) -> Path | None:
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    return Path(to_absolute_path(text))


def _cfg_str(cfg: DictConfig, section: str, key: str, default: str) -> str:
    section_obj = getattr(cfg, section, None)
    if section_obj is None:
        return default
    value = section_obj.get(key, default) if hasattr(section_obj, "get") else getattr(section_obj, key, default)
    return default if value is None else str(value)


def _force_unit_label(cfg: DictConfig) -> str:
    return _cfg_str(cfg, "viewer", "force_unit_label", _cfg_str(cfg, "viewer", "raw_unit_label", "N"))


def _first_scalar(value: Any):
    if isinstance(value, list) and value:
        return _first_scalar(value[0])
    return value


def _required_labels(cfg: DictConfig) -> tuple[str, str, str]:
    return (
        str(cfg.channels.clock_label),
        str(cfg.channels.raw_label),
        str(cfg.channels.filtered_label),
    )


def _rs485_labels(cfg: DictConfig) -> tuple[str, str]:
    return (
        _cfg_str(cfg, "channels", "rs485_raw_label", "rs485_raw"),
        _cfg_str(cfg, "channels", "rs485_clock_label", "rs485_clock"),
    )


def resolve_channel_layout(ch_names: list[str], cfg: DictConfig, *, strict_partial_rs485: bool = True) -> ChannelLayout:
    clock_label, raw_label, filtered_label = _required_labels(cfg)
    rs485_raw_label, rs485_clock_label = _rs485_labels(cfg)

    required = [clock_label, raw_label, filtered_label]
    missing_required = [name for name in required if name not in ch_names]
    if missing_required:
        raise RuntimeError(
            f"Missing required handgrip channels: {missing_required}. Available channels: {ch_names}"
        )

    has_rs485_raw = rs485_raw_label in ch_names
    has_rs485_clock = rs485_clock_label in ch_names
    if has_rs485_raw != has_rs485_clock:
        message = (
            "Partial RS485 schema detected. Both RS485 channels must be present together. "
            f"Expected=({rs485_raw_label}, {rs485_clock_label}); available={ch_names}"
        )
        if strict_partial_rs485:
            raise RuntimeError(message)
        LOGGER.warning("%s Falling back to legacy 3-channel mode.", message)
        has_rs485_raw = False
        has_rs485_clock = False

    return ChannelLayout(
        clock_label=clock_label,
        raw_label=raw_label,
        filtered_label=filtered_label,
        rs485_raw_label=rs485_raw_label,
        rs485_clock_label=rs485_clock_label,
        has_rs485=has_rs485_raw and has_rs485_clock,
    )


def inspect_csv(csv_path: Path) -> list[str]:
    df = pd.read_csv(csv_path, nrows=5)
    columns = list(df.columns)
    LOGGER.info("CSV reference loaded: %s | columns=%s", csv_path, columns)
    missing = [col for col in ["device_clock_us", "value_raw", "value_filtered"] if col not in columns]
    if missing:
        LOGGER.warning("CSV reference is missing expected bridge columns: %s", missing)
    return columns


def inspect_xdf(xdf_path: Path, expected_stream_name: str) -> list[str] | None:
    try:
        import pyxdf  # type: ignore
    except ImportError:
        LOGGER.info("pyxdf is not installed; using lightweight XML metadata scan for %s", xdf_path)
        return inspect_xdf_metadata_fallback(xdf_path, expected_stream_name)

    streams, header = pyxdf.load_xdf(str(xdf_path), dejitter_timestamps=False)
    LOGGER.info("XDF reference loaded: %s | file header keys=%s", xdf_path, list(header.keys()))
    for stream in streams:
        info = stream.get("info", {})
        name = _first_scalar(info.get("name"))
        if name != expected_stream_name:
            continue
        labels = _extract_xdf_labels(info)
        LOGGER.info("XDF stream matched: name=%s | labels=%s", name, labels)
        return labels

    LOGGER.warning("No stream named %s found in XDF file %s", expected_stream_name, xdf_path)
    return None


def inspect_xdf_metadata_fallback(xdf_path: Path, expected_stream_name: str) -> list[str] | None:
    import re

    text = xdf_path.read_bytes().decode("latin1", errors="ignore")
    info_blocks = re.findall(r"<info>.*?</info>", text, flags=re.DOTALL)
    for block in info_blocks:
        name_match = re.search(r"<name>(.*?)</name>", block, flags=re.DOTALL)
        if not name_match or name_match.group(1).strip() != expected_stream_name:
            continue
        labels = [m.strip() for m in re.findall(r"<label>(.*?)</label>", block, flags=re.DOTALL)]
        LOGGER.info("XDF fallback metadata matched: name=%s | labels=%s", expected_stream_name, labels)
        return labels or None
    LOGGER.warning("Fallback XDF metadata scan found no stream named %s in %s", expected_stream_name, xdf_path)
    return None


def _extract_xdf_labels(info: dict[str, Any]) -> list[str] | None:
    desc = info.get("desc", [{}])
    channels = []
    if desc and isinstance(desc, list):
        channels_root = desc[0].get("channels", [{}])
        if channels_root and isinstance(channels_root, list):
            channel_items = channels_root[0].get("channel", [])
            for channel in channel_items:
                label = _first_scalar(channel.get("label"))
                if label is not None:
                    channels.append(str(label))
    return channels or None


def build_stream(cfg: DictConfig):
    try:
        from mne_lsl.stream import StreamLSL
    except ImportError as exc:
        raise RuntimeError(
            "mne-lsl is required for live streaming. Install it with your environment manager before running this viewer."
        ) from exc

    stream = StreamLSL(
        bufsize=int(cfg.stream.buffer_samples),
        name=str(cfg.stream.name),
        stype=str(cfg.stream.stype),
        source_id=None if cfg.stream.source_id is None else str(cfg.stream.source_id),
    )
    stream.connect(
        acquisition_delay=float(cfg.stream.acquisition_delay),
        timeout=float(cfg.stream.timeout),
    )
    return stream


def validate_live_stream(stream, cfg: DictConfig) -> ChannelLayout:
    LOGGER.info(
        "Connected to LSL stream: name=%s type=%s source_id=%s sfreq=%s ch_names=%s",
        stream.name,
        stream.stype,
        stream.source_id,
        stream.info["sfreq"],
        stream.ch_names,
    )
    if float(stream.info["sfreq"]) != 0.0:
        LOGGER.warning(
            "This viewer expects an irregular stream (sfreq=0). Current stream reports sfreq=%s.",
            stream.info["sfreq"],
        )
    layout = resolve_channel_layout(list(stream.ch_names), cfg, strict_partial_rs485=True)
    LOGGER.info("Detected stream schema: %s | picks=%s", layout.schema_name, layout.live_picks)
    return layout


def fetch_live_window(stream, cfg: DictConfig, window_samples: int, layout: ChannelLayout) -> LiveWindow | None:
    data, ts = stream.get_data(winsize=window_samples, picks=layout.live_picks)
    if ts.size == 0:
        return None

    clock = np.asarray(data[0], dtype=np.float64)
    raw = np.asarray(data[1], dtype=np.float64)
    filtered = np.asarray(data[2], dtype=np.float64)
    timestamps = np.asarray(ts, dtype=np.float64)

    rs485_raw = None
    rs485_clock = None
    if layout.has_rs485:
        rs485_raw = np.asarray(data[3], dtype=np.float64)
        rs485_clock = np.asarray(data[4], dtype=np.float64)

    return LiveWindow(
        timestamps_s=timestamps,
        device_clock_us=clock,
        raw=raw,
        filtered=filtered,
        rs485_raw=rs485_raw,
        rs485_clock=rs485_clock,
    )


def _finite_xy(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mask = np.isfinite(x) & np.isfinite(y)
    return x[mask], y[mask]


def update_axis(ax, x: np.ndarray, y: np.ndarray, margin_ratio: float = 0.05) -> None:
    x, y = _finite_xy(np.asarray(x, dtype=np.float64), np.asarray(y, dtype=np.float64))
    if y.size == 0 or x.size == 0:
        return

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
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)


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


def _pick_optional_existing_column(columns: list[str], candidates: list[str]) -> str | None:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return None


def _normalize_timebase(values: np.ndarray, unit_scale_s: float) -> np.ndarray:
    rel = (values.astype(np.float64) - float(values[0])) * unit_scale_s
    finite = rel[np.isfinite(rel)]
    if finite.size >= 2 and np.any(np.diff(finite) < 0):
        raise RuntimeError("Replay timestamps are not monotonic increasing.")
    return rel


def _infer_csv_replay_timestamps(df: pd.DataFrame, cfg: DictConfig) -> np.ndarray:
    time_column = str(cfg.replay.time_column)
    columns = list(df.columns)

    if time_column == "auto":
        if "lsl_timestamp_s" in columns:
            time_column = "lsl_timestamp_s"
        elif "device_clock_us" in columns:
            time_column = "device_clock_us"
        elif "host_unix_time_ns" in columns:
            time_column = "host_unix_time_ns"
        elif bool(cfg.replay.allow_index_fallback):
            time_column = "index"
        else:
            raise RuntimeError(
                "Could not infer CSV replay timebase. Provide replay.time_column explicitly or enable replay.allow_index_fallback."
            )

    if time_column == "index":
        return np.arange(len(df), dtype=np.float64) / float(cfg.viewer.expected_rate_hz)

    if time_column not in columns:
        raise RuntimeError(f"Configured replay.time_column={time_column!r} not found in CSV columns {columns}")

    values = pd.to_numeric(df[time_column], errors="raise").to_numpy(dtype=np.float64)
    if time_column.endswith("_s"):
        return _normalize_timebase(values, 1.0)
    if time_column.endswith("_us"):
        return _normalize_timebase(values, 1e-6)
    if time_column.endswith("_ns"):
        return _normalize_timebase(values, 1e-9)

    unit = str(cfg.replay.time_column_unit)
    if unit == "seconds":
        return _normalize_timebase(values, 1.0)
    if unit == "microseconds":
        return _normalize_timebase(values, 1e-6)
    if unit == "nanoseconds":
        return _normalize_timebase(values, 1e-9)

    raise RuntimeError(
        "Could not infer time units for replay.time_column. Set replay.time_column_unit to seconds, microseconds, or nanoseconds."
    )


def load_csv_replay(cfg: DictConfig) -> ReplayData:
    csv_path = _optional_path(cfg.reference.csv_path)
    if csv_path is None:
        raise RuntimeError("mode=csv_replay requires reference.csv_path")
    df = pd.read_csv(csv_path)
    if df.empty:
        raise RuntimeError(f"CSV replay source is empty: {csv_path}")

    columns = list(df.columns)
    clock_col = _pick_existing_column(
        columns,
        _candidate_columns(str(cfg.channels.clock_label), ["device_clock_us", "clock_us"]),
        "device clock",
    )
    raw_col = _pick_existing_column(
        columns,
        _candidate_columns(str(cfg.channels.raw_label), ["value_raw", "raw", "raw_value"]),
        "raw signal",
    )
    filtered_col = _pick_existing_column(
        columns,
        _candidate_columns(str(cfg.channels.filtered_label), ["value_filtered", "filtered", "filtered_value"]),
        "filtered signal",
    )

    rs485_raw_label, rs485_clock_label = _rs485_labels(cfg)
    rs485_raw_col = _pick_optional_existing_column(
        columns,
        _candidate_columns(rs485_raw_label, ["rs485_value", "reference_raw", "reference_value"]),
    )
    rs485_clock_col = _pick_optional_existing_column(
        columns,
        _candidate_columns(rs485_clock_label, ["rs485_time_s", "reference_clock_s", "reference_time_s"]),
    )
    has_rs485 = rs485_raw_col is not None and rs485_clock_col is not None
    if (rs485_raw_col is None) != (rs485_clock_col is None):
        LOGGER.warning(
            "CSV contains a partial RS485 schema. Falling back to legacy 3-channel replay. "
            "rs485_raw_col=%s rs485_clock_col=%s",
            rs485_raw_col,
            rs485_clock_col,
        )
        has_rs485 = False

    timestamps_s = _infer_csv_replay_timestamps(df, cfg)
    device_clock_us = pd.to_numeric(df[clock_col], errors="raise").to_numpy(dtype=np.float64)
    raw = pd.to_numeric(df[raw_col], errors="raise").to_numpy(dtype=np.float64)
    filtered = pd.to_numeric(df[filtered_col], errors="raise").to_numpy(dtype=np.float64)

    rs485_raw = None
    rs485_clock = None
    if has_rs485:
        rs485_raw = pd.to_numeric(df[rs485_raw_col], errors="coerce").to_numpy(dtype=np.float64)
        rs485_clock = pd.to_numeric(df[rs485_clock_col], errors="coerce").to_numpy(dtype=np.float64)

    selected_labels = [clock_col, raw_col, filtered_col]
    if has_rs485 and rs485_raw_col and rs485_clock_col:
        selected_labels.extend([rs485_raw_col, rs485_clock_col])

    LOGGER.info(
        "CSV replay loaded: %s | samples=%d | schema=%s | timebase=%s | labels=%s",
        csv_path,
        len(df),
        "unified_5ch" if has_rs485 else "legacy_3ch",
        str(cfg.replay.time_column),
        selected_labels,
    )

    return ReplayData(
        timestamps_s=timestamps_s,
        device_clock_us=device_clock_us,
        raw=raw,
        filtered=filtered,
        rs485_raw=rs485_raw,
        rs485_clock=rs485_clock,
        source_name=csv_path.name,
        source_type="csv_replay",
        labels=selected_labels,
    )


def _select_xdf_stream(streams: list[dict[str, Any]], cfg: DictConfig) -> dict[str, Any]:
    matches = []
    for stream in streams:
        info = stream.get("info", {})
        name = _first_scalar(info.get("name"))
        stype = _first_scalar(info.get("type"))
        source_id = _first_scalar(info.get("source_id"))
        if name != str(cfg.stream.name):
            continue
        if stype != str(cfg.stream.stype):
            continue
        if cfg.stream.source_id is not None and source_id != str(cfg.stream.source_id):
            continue
        matches.append(stream)
    if not matches:
        raise RuntimeError(
            f"No XDF stream matched name={cfg.stream.name!r} stype={cfg.stream.stype!r} source_id={cfg.stream.source_id!r}."
        )
    if len(matches) > 1:
        LOGGER.warning("Multiple XDF streams matched; using the first one.")
    return matches[0]


def _extract_xdf_time_series(stream: dict[str, Any]) -> np.ndarray:
    ts = np.asarray(stream.get("time_series"))
    if ts.ndim == 1:
        ts = ts[:, np.newaxis]
    if ts.ndim != 2:
        raise RuntimeError(f"Unsupported XDF time_series shape: {ts.shape}")
    return ts.astype(np.float64)


def _extract_xdf_timestamps(stream: dict[str, Any]) -> np.ndarray:
    stamps = np.asarray(stream.get("time_stamps"), dtype=np.float64)
    if stamps.ndim != 1:
        stamps = stamps.reshape(-1)
    if stamps.size == 0:
        raise RuntimeError("XDF stream contains no timestamps.")
    rel = stamps - float(stamps[0])
    if rel.size >= 2 and np.any(np.diff(rel) < 0):
        raise RuntimeError("XDF replay timestamps are not monotonic increasing.")
    return rel


def _fallback_xdf_labels(time_series: np.ndarray, cfg: DictConfig) -> list[str]:
    clock_label, raw_label, filtered_label = _required_labels(cfg)
    labels = [clock_label, raw_label, filtered_label]
    if time_series.shape[1] >= 5:
        labels.extend(list(_rs485_labels(cfg)))
    return labels


def load_xdf_replay(cfg: DictConfig) -> ReplayData:
    xdf_path = _optional_path(cfg.reference.xdf_path)
    if xdf_path is None:
        raise RuntimeError("mode=xdf_replay requires reference.xdf_path")
    try:
        import pyxdf  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "mode=xdf_replay requires pyxdf. Install it before using XDF replay."
        ) from exc

    streams, header = pyxdf.load_xdf(str(xdf_path), dejitter_timestamps=False)
    LOGGER.info("XDF replay loaded: %s | file header keys=%s | streams=%d", xdf_path, list(header.keys()), len(streams))
    stream = _select_xdf_stream(streams, cfg)
    info = stream.get("info", {})
    labels = _extract_xdf_labels(info) or []
    time_series = _extract_xdf_time_series(stream)
    timestamps_s = _extract_xdf_timestamps(stream)

    if labels and time_series.shape[1] != len(labels):
        LOGGER.warning(
            "XDF label count does not match channel count: labels=%d channels=%d. Falling back to positional labels.",
            len(labels),
            time_series.shape[1],
        )
        labels = []

    if not labels:
        labels = _fallback_xdf_labels(time_series, cfg)

    if time_series.shape[1] < 3:
        raise RuntimeError(f"Expected at least 3 numeric channels in XDF replay stream, got shape={time_series.shape}")

    try:
        clock_idx = labels.index(str(cfg.channels.clock_label))
        raw_idx = labels.index(str(cfg.channels.raw_label))
        filtered_idx = labels.index(str(cfg.channels.filtered_label))
    except ValueError as exc:
        raise RuntimeError(
            f"XDF replay stream labels do not contain the configured handgrip channels. labels={labels}"
        ) from exc

    rs485_raw = None
    rs485_clock = None
    rs485_raw_label, rs485_clock_label = _rs485_labels(cfg)
    has_rs485_raw = rs485_raw_label in labels
    has_rs485_clock = rs485_clock_label in labels
    if has_rs485_raw != has_rs485_clock:
        raise RuntimeError(
            "Partial RS485 schema detected in XDF replay. "
            f"Expected both {rs485_raw_label!r} and {rs485_clock_label!r}; labels={labels}"
        )
    if has_rs485_raw and has_rs485_clock:
        rs485_raw_idx = labels.index(rs485_raw_label)
        rs485_clock_idx = labels.index(rs485_clock_label)
        rs485_raw = time_series[:, rs485_raw_idx].astype(np.float64)
        rs485_clock = time_series[:, rs485_clock_idx].astype(np.float64)

    device_clock_us = time_series[:, clock_idx].astype(np.float64)
    raw = time_series[:, raw_idx].astype(np.float64)
    filtered = time_series[:, filtered_idx].astype(np.float64)

    LOGGER.info(
        "XDF replay selected stream: name=%s | schema=%s | labels=%s",
        str(_first_scalar(info.get("name")) or xdf_path.name),
        "unified_5ch" if rs485_raw is not None else "legacy_3ch",
        labels,
    )

    return ReplayData(
        timestamps_s=timestamps_s,
        device_clock_us=device_clock_us,
        raw=raw,
        filtered=filtered,
        rs485_raw=rs485_raw,
        rs485_clock=rs485_clock,
        source_name=str(_first_scalar(info.get("name")) or xdf_path.name),
        source_type=str(_first_scalar(info.get("type")) or "xdf_replay"),
        source_id=None if _first_scalar(info.get("source_id")) is None else str(_first_scalar(info.get("source_id"))),
        labels=labels,
    )


def inspect_references_if_enabled(cfg: DictConfig, mode: str) -> OfflineReference:
    reference = OfflineReference()
    do_validation = mode == "live_with_reference_validation" or bool(cfg.reference.inspect_in_replay_modes)
    if not do_validation:
        return reference

    csv_path = _optional_path(cfg.reference.csv_path)
    if csv_path is not None:
        reference.csv_path = csv_path
        reference.csv_columns = inspect_csv(csv_path)

    xdf_path = _optional_path(cfg.reference.xdf_path)
    if xdf_path is not None:
        reference.xdf_path = xdf_path
        reference.xdf_labels = inspect_xdf(xdf_path, str(cfg.stream.name))

    return reference


def init_figure(cfg: DictConfig, has_rs485: bool) -> FigureHandles:
    force_unit = _force_unit_label(cfg)
    dt_unit = str(cfg.viewer.dt_unit_label)

    if has_rs485:
        fig = plt.figure(figsize=(14, 13), constrained_layout=False)
        gs = fig.add_gridspec(
            5,
            2,
            height_ratios=[1.15, 2.0, 2.0, 2.0, 2.4],
            hspace=0.58,
            wspace=0.30,
        )
        axes = {
            "info": fig.add_subplot(gs[0, :]),
            "raw": fig.add_subplot(gs[1, 0]),
            "rs485_raw": fig.add_subplot(gs[1, 1]),
            "filtered": fig.add_subplot(gs[2, 0]),
            "overlay": fig.add_subplot(gs[2, 1]),
            "handgrip_dt": fig.add_subplot(gs[3, 0]),
            "rs485_dt": fig.add_subplot(gs[3, 1]),
            "xy": fig.add_subplot(gs[4, :]),
        }
        artists: dict[str, Any] = {}
        (artists["raw"],) = axes["raw"].plot([], [], color=RAW_COLOR, label="handgrip raw", linewidth=1.0)
        (artists["rs485_raw"],) = axes["rs485_raw"].plot([], [], color=RAW_COLOR, label="RS485 raw", linewidth=1.0)
        (artists["filtered"],) = axes["filtered"].plot([], [], color=FILTERED_COLOR, label="handgrip filtered", linewidth=1.2)
        (artists["overlay_hg"],) = axes["overlay"].plot([], [], color=RAW_COLOR, label="handgrip raw", linewidth=1.0)
        (artists["overlay_rs"],) = axes["overlay"].plot([], [], color=RAW_COLOR, linestyle="--", label="RS485 raw", linewidth=1.0)
        (artists["handgrip_dt"],) = axes["handgrip_dt"].plot([], [], color=TIMING_COLOR, label="handgrip dt", linewidth=1.0)
        (artists["rs485_dt"],) = axes["rs485_dt"].plot([], [], color=TIMING_COLOR, label="RS485 dt", linewidth=1.0)
        artists["xy"] = axes["xy"].scatter([], [], s=12, alpha=0.7, label="current window")

        axes["raw"].set_title("Handgrip raw signal")
        axes["rs485_raw"].set_title("RS485 raw signal")
        axes["filtered"].set_title("Handgrip filtered signal")
        axes["overlay"].set_title("Time-synchronized raw overlay")
        axes["handgrip_dt"].set_title("Handgrip sample interval")
        axes["rs485_dt"].set_title("RS485 sample interval")
        axes["xy"].set_title("XY correlation: Handgrip raw vs RS485 raw")

        for key in ["raw", "rs485_raw", "filtered", "overlay"]:
            axes[key].set_ylabel(f"Force ({force_unit})")
        axes["handgrip_dt"].set_ylabel(f"Interval ({dt_unit})")
        axes["rs485_dt"].set_ylabel(f"Interval ({dt_unit})")
        axes["raw"].set_xlabel("Relative time (s)")
        axes["rs485_raw"].set_xlabel("Relative time (s)")
        axes["filtered"].set_xlabel("Relative time (s)")
        axes["overlay"].set_xlabel("Device-relative time (s)")
        axes["handgrip_dt"].set_xlabel("Relative time (s)")
        axes["rs485_dt"].set_xlabel("Relative time (s)")
        axes["xy"].set_xlabel(f"Handgrip raw force ({force_unit})")
        axes["xy"].set_ylabel(f"RS485 raw force ({force_unit})")

        for key, ax in axes.items():
            if key == "info":
                continue
            ax.grid(True, alpha=GRID_ALPHA)
            ax.legend(loc="upper right")
    else:
        fig, axes_array = plt.subplots(
            4,
            1,
            figsize=(12, 10),
            constrained_layout=False,
            gridspec_kw={"height_ratios": [1.35, 3.0, 3.0, 3.0]},
        )
        plt.subplots_adjust(top=0.96, bottom=0.06, left=0.1, right=0.95, hspace=0.42)
        axes = {
            "info": axes_array[0],
            "raw": axes_array[1],
            "filtered": axes_array[2],
            "handgrip_dt": axes_array[3],
        }
        artists = {}
        (artists["raw"],) = axes["raw"].plot([], [], color=RAW_COLOR, label="handgrip raw", linewidth=1.0)
        (artists["filtered"],) = axes["filtered"].plot([], [], color=FILTERED_COLOR, label="handgrip filtered", linewidth=1.2)
        (artists["handgrip_dt"],) = axes["handgrip_dt"].plot([], [], color=TIMING_COLOR, label="handgrip dt", linewidth=1.0)

        axes["raw"].set_title("Handgrip raw signal")
        axes["filtered"].set_title("Handgrip filtered signal")
        axes["handgrip_dt"].set_title("Handgrip sample interval")
        axes["raw"].set_ylabel(f"Force ({force_unit})")
        axes["filtered"].set_ylabel(f"Force ({force_unit})")
        axes["handgrip_dt"].set_ylabel(f"Interval ({dt_unit})")
        axes["handgrip_dt"].set_xlabel("Relative time (s)")
        for key in ["raw", "filtered", "handgrip_dt"]:
            axes[key].grid(True, alpha=GRID_ALPHA)
            axes[key].legend(loc="upper right")

    axes["info"].axis("off")
    axes["info"].set_xlim(0, 1)
    axes["info"].set_ylim(0, 1)
    axes["info"].set_title("Stream Overview", loc="left", pad=6)
    return FigureHandles(fig=fig, axes=axes, artists=artists)


def _format_reference_summary(reference: OfflineReference) -> str:
    return f"csv_ref={reference.csv_path if reference.csv_path else 'none'}   xdf_ref={reference.xdf_path if reference.xdf_path else 'none'}"


def _relative_to_last_finite(values: np.ndarray, scale: float = 1.0) -> np.ndarray:
    arr = np.asarray(values, dtype=np.float64) * scale
    rel = np.full_like(arr, np.nan, dtype=np.float64)
    finite_idx = np.flatnonzero(np.isfinite(arr))
    if finite_idx.size == 0:
        return rel
    rel[finite_idx] = arr[finite_idx] - arr[finite_idx[-1]]
    return rel


def _clock_interval_ms(clock: np.ndarray, scale_to_ms: float) -> tuple[np.ndarray, np.ndarray, float, float]:
    clock = np.asarray(clock, dtype=np.float64)
    if clock.size < 2:
        return np.array([], dtype=np.float64), np.array([], dtype=np.float64), float("nan"), float("nan")
    finite = np.isfinite(clock)
    valid_indices = np.flatnonzero(finite)
    if valid_indices.size < 2:
        return np.array([], dtype=np.float64), np.array([], dtype=np.float64), float("nan"), float("nan")

    c = clock[valid_indices]
    dt_ms = np.diff(c) * scale_to_ms
    second_indices = valid_indices[1:]
    valid_dt = np.isfinite(dt_ms) & (dt_ms > 0)
    dt_ms = dt_ms[valid_dt]
    second_indices = second_indices[valid_dt]
    if dt_ms.size == 0:
        return second_indices.astype(np.float64), dt_ms, float("nan"), float("nan")
    rate_hz = 1000.0 / float(np.median(dt_ms))
    mean_dt_ms = float(np.mean(dt_ms))
    return second_indices.astype(np.float64), dt_ms, rate_hz, mean_dt_ms


def _interpolated_xy(window: LiveWindow) -> tuple[np.ndarray, np.ndarray]:
    if not window.has_rs485:
        return np.array([], dtype=np.float64), np.array([], dtype=np.float64)

    t_hg = _relative_to_last_finite(window.device_clock_us, 1e-6)
    t_rs = _relative_to_last_finite(window.rs485_clock, 1.0)

    hg_mask = np.isfinite(t_hg) & np.isfinite(window.raw)
    rs_mask = np.isfinite(t_rs) & np.isfinite(window.rs485_raw)
    if np.count_nonzero(hg_mask) < 2 or np.count_nonzero(rs_mask) < 2:
        return np.array([], dtype=np.float64), np.array([], dtype=np.float64)

    hg_t = t_hg[hg_mask]
    hg_y = window.raw[hg_mask]
    rs_t = t_rs[rs_mask]
    rs_y = window.rs485_raw[rs_mask]

    order = np.argsort(rs_t)
    rs_t = rs_t[order]
    rs_y = rs_y[order]
    unique = np.r_[True, np.diff(rs_t) > 0]
    rs_t = rs_t[unique]
    rs_y = rs_y[unique]
    if rs_t.size < 2:
        return np.array([], dtype=np.float64), np.array([], dtype=np.float64)

    inside = (hg_t >= rs_t[0]) & (hg_t <= rs_t[-1])
    if np.count_nonzero(inside) < 2:
        return np.array([], dtype=np.float64), np.array([], dtype=np.float64)

    xy_x = hg_y[inside]
    xy_y = np.interp(hg_t[inside], rs_t, rs_y)
    finite = np.isfinite(xy_x) & np.isfinite(xy_y)
    return xy_x[finite], xy_y[finite]


def _update_xy_scatter(scatter, x: np.ndarray, y: np.ndarray) -> None:
    if x.size == 0 or y.size == 0:
        scatter.set_offsets(np.empty((0, 2)))
        scatter.set_facecolors(np.empty((0, 4)))
        return
    offsets = np.column_stack([x, y])
    rgba = np.tile(mcolors.to_rgba(RAW_COLOR), (x.size, 1))
    rgba[:, 3] = np.linspace(0.10, 0.85, x.size)
    scatter.set_offsets(offsets)
    scatter.set_facecolors(rgba)
    scatter.set_edgecolors("none")


def _zip_columns(*cols: str) -> str:
    sections = [c.split("\n") for c in cols]
    col_widths = [max(len(line) for line in s) + 2 for s in sections]
    max_lines = max(len(s) for s in sections)
    for s in sections:
        while len(s) < max_lines:
            s.append("")
    rows = []
    for i in range(max_lines):
        row = ""
        for j, lines in enumerate(sections):
            row += f"{lines[i]:<{col_widths[j]}}"
        rows.append(row.rstrip())
    return "\n".join(rows)


def _format_latest(value: float | None, suffix: str = "", precision: int = 3) -> str:
    if value is None or not np.isfinite(value):
        return "nan"
    return f"{value:.{precision}f}{suffix}"


def _valid_percentage(*arrays: np.ndarray | None) -> float:
    present = [a for a in arrays if a is not None]
    if not present:
        return float("nan")
    mask = np.ones_like(present[0], dtype=bool)
    for arr in present:
        mask &= np.isfinite(arr)
    return 100.0 * float(np.count_nonzero(mask)) / float(mask.size) if mask.size else float("nan")


def _render_info_panel(
    handles: FigureHandles,
    text: str,
    *,
    font_size: int,
) -> None:
    ax_info = handles.axes["info"]
    ax_info.clear()
    ax_info.axis("off")
    ax_info.set_xlim(0, 1)
    ax_info.set_ylim(0, 1)
    ax_info.set_title("Stream Overview", loc="left", pad=6)
    ax_info.text(
        0.02,
        0.88,
        text,
        va="top",
        ha="left",
        family="monospace",
        fontsize=font_size,
        transform=ax_info.transAxes,
    )


def update_plots(
    handles: FigureHandles,
    window: LiveWindow,
    cfg: DictConfig,
    *,
    source_name: str,
    source_type: str | None,
    source_id: str | None,
    mode: str,
    schema_name: str,
    channel_names: list[str] | None = None,
    new_samples: int | None = None,
    replay_progress_text: str | None = None,
) -> None:
    force_unit = _force_unit_label(cfg)
    t_rel_lsl = window.timestamps_s - window.timestamps_s[-1]

    # Core 3-channel plots.
    handles.artists["raw"].set_data(t_rel_lsl, window.raw)
    handles.artists["filtered"].set_data(t_rel_lsl, window.filtered)
    update_axis(handles.axes["raw"], t_rel_lsl, window.raw)
    update_axis(handles.axes["filtered"], t_rel_lsl, window.filtered)

    hg_dt_indices, hg_dt_ms, hg_rate_hz, hg_mean_dt_ms = _clock_interval_ms(window.device_clock_us, 1e-3)
    if hg_dt_ms.size:
        hg_dt_t_rel = t_rel_lsl[hg_dt_indices.astype(int)]
        handles.artists["handgrip_dt"].set_data(hg_dt_t_rel, hg_dt_ms)
        update_axis(handles.axes["handgrip_dt"], hg_dt_t_rel, hg_dt_ms)
    else:
        handles.artists["handgrip_dt"].set_data([], [])

    # Optional unified 5-channel plots.
    rs_rate_hz = float("nan")
    rs_mean_dt_ms = float("nan")
    rs_valid_pct = float("nan")
    if window.has_rs485 and "rs485_raw" in handles.artists:
        handles.artists["rs485_raw"].set_data(t_rel_lsl, window.rs485_raw)
        update_axis(handles.axes["rs485_raw"], t_rel_lsl, window.rs485_raw)

        rs_dt_indices, rs_dt_ms, rs_rate_hz, rs_mean_dt_ms = _clock_interval_ms(window.rs485_clock, 1000.0)
        if rs_dt_ms.size:
            rs_dt_t_rel = t_rel_lsl[rs_dt_indices.astype(int)]
            handles.artists["rs485_dt"].set_data(rs_dt_t_rel, rs_dt_ms)
            update_axis(handles.axes["rs485_dt"], rs_dt_t_rel, rs_dt_ms)
        else:
            handles.artists["rs485_dt"].set_data([], [])

        t_hg_rel = _relative_to_last_finite(window.device_clock_us, 1e-6)
        t_rs_rel = _relative_to_last_finite(window.rs485_clock, 1.0)
        handles.artists["overlay_hg"].set_data(t_hg_rel, window.raw)
        handles.artists["overlay_rs"].set_data(t_rs_rel, window.rs485_raw)
        overlay_x = np.concatenate([t_hg_rel[np.isfinite(t_hg_rel)], t_rs_rel[np.isfinite(t_rs_rel)]])
        overlay_y = np.concatenate([window.raw[np.isfinite(t_hg_rel) & np.isfinite(window.raw)], window.rs485_raw[np.isfinite(t_rs_rel) & np.isfinite(window.rs485_raw)]])
        if overlay_x.size and overlay_y.size:
            update_axis(handles.axes["overlay"], overlay_x, overlay_y)

        xy_x, xy_y = _interpolated_xy(window)
        _update_xy_scatter(handles.artists["xy"], xy_x, xy_y)
        if xy_x.size:
            update_axis(handles.axes["xy"], xy_x, xy_y)

        rs_valid_pct = _valid_percentage(window.rs485_raw, window.rs485_clock)

    channels_text = "none"
    if channel_names:
        channels_text = "- " + "\n- ".join(channel_names)

    col_source = (
        "SOURCE/MODE\n"
        f"name   : {source_name}\n"
        f"type   : {source_type}\n"
        f"id     : {source_id}\n"
        f"mode   : {mode}\n"
        f"schema : {schema_name}"
    )
    col_hg = (
        f"HANDGRIP ({force_unit})\n"
        f"raw    : {_format_latest(float(window.raw[-1]), precision=3)}\n"
        f"filt   : {_format_latest(float(window.filtered[-1]), precision=3)}\n"
        f"clock  : {_format_latest(float(window.device_clock_us[-1]), ' us', precision=0)}\n"
        f"rate   : {_format_latest(hg_rate_hz, ' Hz', precision=2)}\n"
        f"dt     : {_format_latest(hg_mean_dt_ms, ' ms', precision=2)}"
    )

    if window.has_rs485:
        latest_rs_raw = float(window.rs485_raw[-1]) if window.rs485_raw is not None else float("nan")
        latest_rs_clock = float(window.rs485_clock[-1]) if window.rs485_clock is not None else float("nan")
        col_rs = (
            f"RS485 ({force_unit})\n"
            f"raw    : {_format_latest(latest_rs_raw, precision=3)}\n"
            f"clock  : {_format_latest(latest_rs_clock, ' s', precision=6)}\n"
            f"rate   : {_format_latest(rs_rate_hz, ' Hz', precision=2)}\n"
            f"dt     : {_format_latest(rs_mean_dt_ms, ' ms', precision=2)}\n"
            f"valid  : {_format_latest(rs_valid_pct, ' %', precision=1)}"
        )
    else:
        col_rs = "RS485\nstatus : unavailable"

    col_metrics = "METRICS\n"
    if new_samples is not None:
        col_metrics += f"new    : {new_samples}\n"
    if replay_progress_text:
        col_metrics += replay_progress_text
    else:
        col_metrics += f"window : {window.timestamps_s.size} samples"

    col_channels = f"CHANNELS\n{channels_text}"
    font_size = 8 if window.has_rs485 else 10
    latest_text = _zip_columns(col_source, col_hg, col_rs, col_metrics, col_channels)
    _render_info_panel(handles, latest_text, font_size=font_size)


def run_live_mode(cfg: DictConfig, reference: OfflineReference, validate_reference: bool) -> int:
    window_samples = infer_window_samples(cfg)
    stream = build_stream(cfg)
    layout = validate_live_stream(stream, cfg)
    handles = init_figure(cfg, has_rs485=layout.has_rs485)

    LOGGER.info(
        "Live viewer started: mode=%s schema=%s buffer_samples=%d window_samples=%d refresh_s=%.3f reference=%s",
        "live_with_reference_validation" if validate_reference else "live",
        layout.schema_name,
        int(cfg.stream.buffer_samples),
        window_samples,
        float(cfg.viewer.refresh_s),
        _format_reference_summary(reference),
    )

    try:
        while plt.fignum_exists(handles.fig.number):
            live = fetch_live_window(stream, cfg, window_samples, layout)
            if live is None:
                plt.pause(float(cfg.viewer.refresh_s))
                continue

            update_plots(
                handles,
                live,
                cfg,
                source_name=str(stream.name),
                source_type=str(stream.stype),
                source_id=None if stream.source_id is None else str(stream.source_id),
                mode="live_ref" if validate_reference else "live",
                schema_name=layout.schema_name,
                channel_names=list(stream.ch_names),
                new_samples=int(stream.n_new_samples),
            )
            plt.pause(float(cfg.viewer.refresh_s))

    except KeyboardInterrupt:
        LOGGER.info("Stopping on user request")
    finally:
        stream.disconnect()
        plt.close(handles.fig)

    return 0


def _window_from_replay(data: ReplayData, end_index: int, window_samples: int) -> LiveWindow | None:
    end_index = max(0, min(end_index, data.timestamps_s.size))
    if end_index == 0:
        return None
    start_index = max(0, end_index - window_samples)
    rs485_raw = None
    rs485_clock = None
    if data.rs485_raw is not None and data.rs485_clock is not None:
        rs485_raw = data.rs485_raw[start_index:end_index]
        rs485_clock = data.rs485_clock[start_index:end_index]

    return LiveWindow(
        timestamps_s=data.timestamps_s[start_index:end_index],
        device_clock_us=data.device_clock_us[start_index:end_index],
        raw=data.raw[start_index:end_index],
        filtered=data.filtered[start_index:end_index],
        rs485_raw=rs485_raw,
        rs485_clock=rs485_clock,
    )


def run_replay_mode(cfg: DictConfig, replay_data: ReplayData, reference: OfflineReference, mode: str) -> int:
    window_samples = infer_window_samples(cfg)
    handles = init_figure(cfg, has_rs485=replay_data.has_rs485)

    timestamps = replay_data.timestamps_s
    if timestamps.size == 0:
        raise RuntimeError(f"Replay dataset is empty for mode={mode}")

    start_offset_s = max(0.0, float(cfg.replay.start_offset_s))
    replay_speed = max(1e-9, float(cfg.replay.speed))
    loop = bool(cfg.replay.loop)

    LOGGER.info(
        "Replay viewer started: mode=%s source=%s schema=%s samples=%d window_samples=%d refresh_s=%.3f speed=%.3f loop=%s reference=%s",
        mode,
        replay_data.source_name,
        replay_data.schema_name,
        timestamps.size,
        window_samples,
        float(cfg.viewer.refresh_s),
        replay_speed,
        loop,
        _format_reference_summary(reference),
    )

    replay_start_wall = time.monotonic()
    target_index = 0

    try:
        while plt.fignum_exists(handles.fig.number):
            elapsed_s = (time.monotonic() - replay_start_wall) * replay_speed + start_offset_s
            if loop and timestamps[-1] > 0:
                elapsed_s = elapsed_s % float(timestamps[-1])
            target_index = int(np.searchsorted(timestamps, elapsed_s, side="right"))
            if target_index <= 0:
                plt.pause(float(cfg.viewer.refresh_s))
                continue
            if target_index >= timestamps.size and not loop:
                target_index = timestamps.size

            window = _window_from_replay(replay_data, target_index, window_samples)
            if window is None:
                plt.pause(float(cfg.viewer.refresh_s))
                continue

            replay_progress = (
                f"pos    : {target_index}/{timestamps.size}\n"
                f"time   : {elapsed_s:.2f} s\n"
                f"speed  : {replay_speed:.2f}x"
            )
            update_plots(
                handles,
                window,
                cfg,
                source_name=replay_data.source_name,
                source_type=replay_data.source_type,
                source_id=replay_data.source_id,
                mode=mode,
                schema_name=replay_data.schema_name,
                channel_names=replay_data.labels,
                replay_progress_text=replay_progress,
            )
            plt.pause(float(cfg.viewer.refresh_s))
            if target_index >= timestamps.size and not loop:
                LOGGER.info("Replay reached the end of the dataset; holding final frame.")
                break

        while plt.fignum_exists(handles.fig.number) and not loop and target_index >= timestamps.size:
            plt.pause(float(cfg.viewer.refresh_s))

    except KeyboardInterrupt:
        LOGGER.info("Stopping on user request")
    finally:
        plt.close(handles.fig)

    return 0


@hydra.main(version_base=None, config_path="conf", config_name="config")
def app(cfg: DictConfig) -> int:
    configure_logging(str(cfg.logging.level))
    LOGGER.info("Starting viewer with config:\n%s", OmegaConf.to_yaml(cfg, resolve=True))

    mode = str(cfg.mode)
    if mode not in ALLOWED_MODES:
        raise RuntimeError(f"Unsupported mode={mode!r}. Allowed modes: {sorted(ALLOWED_MODES)}")

    reference = inspect_references_if_enabled(cfg, mode)

    if mode == "live":
        return run_live_mode(cfg, reference, validate_reference=False)
    if mode == "live_with_reference_validation":
        return run_live_mode(cfg, reference, validate_reference=True)
    if mode == "csv_replay":
        replay_data = load_csv_replay(cfg)
        return run_replay_mode(cfg, replay_data, reference, mode)
    if mode == "xdf_replay":
        replay_data = load_xdf_replay(cfg)
        return run_replay_mode(cfg, replay_data, reference, mode)

    raise AssertionError("Unreachable mode dispatch")


if __name__ == "__main__":
    raise SystemExit(app())
