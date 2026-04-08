from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import hydra
import matplotlib
matplotlib.use('Qt5Agg')
import numpy as np
import pandas as pd
from hydra.utils import to_absolute_path
from matplotlib import pyplot as plt
from omegaconf import DictConfig, OmegaConf

LOGGER = logging.getLogger("handgrip_realtime_viewer")


@dataclass(slots=True)
class OfflineReference:
    csv_columns: list[str] | None = None
    csv_path: Path | None = None
    xdf_labels: list[str] | None = None
    xdf_path: Path | None = None


@dataclass(slots=True)
class LiveWindow:
    timestamps_s: np.ndarray
    device_clock_us: np.ndarray
    raw: np.ndarray
    filtered: np.ndarray


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


def _first_scalar(value: Any):
    if isinstance(value, list) and value:
        return _first_scalar(value[0])
    return value


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


def validate_live_stream(stream, cfg: DictConfig) -> None:
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
    expected = [
        str(cfg.channels.clock_label),
        str(cfg.channels.raw_label),
        str(cfg.channels.filtered_label),
    ]
    missing = [name for name in expected if name not in stream.ch_names]
    if missing:
        raise RuntimeError(
            f"Connected stream does not contain the expected channels {missing}. Available channels: {stream.ch_names}"
        )


def fetch_live_window(stream, cfg: DictConfig, window_samples: int) -> LiveWindow | None:
    picks = [
        str(cfg.channels.clock_label),
        str(cfg.channels.raw_label),
        str(cfg.channels.filtered_label),
    ]
    data, ts = stream.get_data(winsize=window_samples, picks=picks)
    if ts.size == 0:
        return None

    clock = np.asarray(data[0], dtype=np.float64)
    raw = np.asarray(data[1], dtype=np.float64)
    filtered = np.asarray(data[2], dtype=np.float64)
    timestamps = np.asarray(ts, dtype=np.float64)
    return LiveWindow(timestamps_s=timestamps, device_clock_us=clock, raw=raw, filtered=filtered)


def update_axis(ax, x: np.ndarray, y: np.ndarray, margin_ratio: float = 0.05) -> None:
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
    ax.set_xlim(float(x[0]), float(x[-1]))
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


def _normalize_timebase(values: np.ndarray, unit_scale_s: float) -> np.ndarray:
    rel = (values.astype(np.float64) - float(values[0])) * unit_scale_s
    if rel.size >= 2 and np.any(np.diff(rel) < 0):
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

    if str(cfg.replay.time_column_unit) == "seconds":
        return _normalize_timebase(values, 1.0)
    if str(cfg.replay.time_column_unit) == "microseconds":
        return _normalize_timebase(values, 1e-6)
    if str(cfg.replay.time_column_unit) == "nanoseconds":
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

    timestamps_s = _infer_csv_replay_timestamps(df, cfg)
    device_clock_us = pd.to_numeric(df[clock_col], errors="raise").to_numpy(dtype=np.float64)
    raw = pd.to_numeric(df[raw_col], errors="raise").to_numpy(dtype=np.float64)
    filtered = pd.to_numeric(df[filtered_col], errors="raise").to_numpy(dtype=np.float64)

    LOGGER.info(
        "CSV replay loaded: %s | samples=%d | timebase=%s | columns={clock=%s, raw=%s, filtered=%s}",
        csv_path,
        len(df),
        str(cfg.replay.time_column),
        clock_col,
        raw_col,
        filtered_col,
    )

    return ReplayData(
        timestamps_s=timestamps_s,
        device_clock_us=device_clock_us,
        raw=raw,
        filtered=filtered,
        source_name=csv_path.name,
        source_type="csv_replay",
        labels=[clock_col, raw_col, filtered_col],
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
        labels = [str(cfg.channels.clock_label), str(cfg.channels.raw_label), str(cfg.channels.filtered_label)]

    if time_series.shape[1] < 3:
        raise RuntimeError(f"Expected at least 3 numeric channels in XDF replay stream, got shape={time_series.shape}")

    try:
        clock_idx = labels.index(str(cfg.channels.clock_label))
        raw_idx = labels.index(str(cfg.channels.raw_label))
        filtered_idx = labels.index(str(cfg.channels.filtered_label))
    except ValueError as exc:
        raise RuntimeError(
            f"XDF replay stream labels do not contain the configured channels. labels={labels}"
        ) from exc

    device_clock_us = time_series[:, clock_idx].astype(np.float64)
    raw = time_series[:, raw_idx].astype(np.float64)
    filtered = time_series[:, filtered_idx].astype(np.float64)

    return ReplayData(
        timestamps_s=timestamps_s,
        device_clock_us=device_clock_us,
        raw=raw,
        filtered=filtered,
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


def init_figure(cfg: DictConfig):
    fig, axes = plt.subplots(
        4,
        1,
        figsize=(12, 10),
        constrained_layout=False,
        gridspec_kw={"height_ratios": [1.35, 3.0, 3.0, 3.0]},
    )
    plt.subplots_adjust(top=0.96, bottom=0.06, left=0.1, right=0.95, hspace=0.42)

    ax_info, ax_raw, ax_filtered, ax_dt = axes

    ax_raw.sharex(ax_filtered)
    ax_filtered.sharex(ax_dt)
    (line_raw,) = ax_raw.plot([], [], label="raw", linewidth=1.0)
    (line_filtered,) = ax_filtered.plot([], [], label="filtered", linewidth=1.2)
    (line_dt,) = ax_dt.plot([], [], label="device dt (ms)", linewidth=1.0)

    ax_raw.set_title("Handgrip raw signal")
    ax_filtered.set_title("Handgrip filtered signal")
    ax_dt.set_title("Device sample interval")
    ax_raw.set_ylabel(str(cfg.viewer.raw_unit_label))
    ax_filtered.set_ylabel(str(cfg.viewer.filtered_unit_label))
    ax_dt.set_ylabel(str(cfg.viewer.dt_unit_label))
    ax_dt.set_xlabel("Relative time (s)")
    for ax in [ax_raw, ax_filtered, ax_dt]:
        ax.grid(True, alpha=0.3)
        ax.legend(loc="upper right")  # Moved legend to avoid text overlap
    
    ax_info.axis("off")
    ax_info.set_xlim(0, 1)
    ax_info.set_ylim(0, 1)
    ax_info.set_title("Stream Overview", loc="left", pad=6)
    
    return fig, axes, line_raw, line_filtered, line_dt, ax_info


def _format_reference_summary(reference: OfflineReference) -> str:
    return f"csv_ref={reference.csv_path if reference.csv_path else 'none'}   xdf_ref={reference.xdf_path if reference.xdf_path else 'none'}"


def run_live_mode(cfg: DictConfig, reference: OfflineReference, validate_reference: bool) -> int:
    window_samples = infer_window_samples(cfg)
    stream = build_stream(cfg)
    validate_live_stream(stream, cfg)
    fig, axes, line_raw, line_filtered, line_dt, ax_info = init_figure(cfg)
    _, ax_raw, ax_filtered, ax_dt = axes

    LOGGER.info(
        "Live viewer started: mode=%s buffer_samples=%d window_samples=%d refresh_s=%.3f",
        "live_with_reference_validation" if validate_reference else "live",
        int(cfg.stream.buffer_samples),
        window_samples,
        float(cfg.viewer.refresh_s),
    )

    try:
        while plt.fignum_exists(fig.number):
            live = fetch_live_window(stream, cfg, window_samples)
            if live is None:
                plt.pause(float(cfg.viewer.refresh_s))
                continue

            t_rel = live.timestamps_s - live.timestamps_s[-1]
            line_raw.set_data(t_rel, live.raw)
            line_filtered.set_data(t_rel, live.filtered)
            update_axis(ax_raw, t_rel, live.raw)
            update_axis(ax_filtered, t_rel, live.filtered)

            if live.device_clock_us.size >= 2:
                device_dt_ms = np.diff(live.device_clock_us) / 1000.0
                dt_t_rel = t_rel[1:]
                line_dt.set_data(dt_t_rel, device_dt_ms)
                update_axis(ax_dt, dt_t_rel, device_dt_ms)
                observed_rate_hz = 1000.0 / float(np.median(device_dt_ms)) if np.all(device_dt_ms > 0) else float("nan")
                mean_dt_ms = float(np.mean(device_dt_ms))
            else:
                line_dt.set_data([], [])
                observed_rate_hz = float("nan")
                mean_dt_ms = float("nan")

            # Column-based layout for live mode
            col_source = (
                f"SOURCE/MODE\n"
                f"name : {stream.name}\n"
                f"type : {stream.stype}\n"
                f"id   : {stream.source_id}\n"
                f"mode : {'live_ref' if validate_reference else 'live'}"
            )
            col_signal = (
                f"SIGNAL ({cfg.viewer.raw_unit_label}/{cfg.viewer.filtered_unit_label})\n"
                f"raw    : {live.raw[-1]:.3f}\n"
                f"filt   : {live.filtered[-1]:.2f}\n"
                f"clock  : {live.device_clock_us[-1]:.0f} us"
            )
            col_metrics = (
                f"METRICS\n"
                f"rate   : {observed_rate_hz:.2f} Hz\n"
                f"dt     : {mean_dt_ms:.2f} ms\n"
                f"new    : {stream.n_new_samples}"
            )
            col_channels = (
                f"CHANNELS\n"
                f"- {'\n- '.join(stream.ch_names)}"
            )

            # We use a single line for each category, but they are displayed as columns
            def _zip_columns(*cols):
                # Dynamically determine the maximum width for each column based on its content
                col_lines = [c.split('\n') for c in cols]
                col_widths = [max(len(line) for line in lines) + 2 for lines in col_lines]
                
                max_lines = max(len(lines) for lines in col_lines)
                # Pad with empty strings
                for cl in col_lines:
                    while len(cl) < max_lines:
                        cl.append("")
                
                res = []
                for i in range(max_lines):
                    row = ""
                    for j, lines in enumerate(col_lines):
                        w = col_widths[j]
                        # Ensure the text doesn't overflow the calculated width (though here it's derived from it)
                        text = lines[i][:w]
                        row += f"{text:<{w}}"
                    res.append(row.rstrip())
                return "\n".join(res)

            latest_text = _zip_columns(col_source, col_signal, col_metrics, col_channels)
            ax_info.clear()
            ax_info.axis("off")
            ax_info.set_xlim(0, 1)
            ax_info.set_ylim(0, 1)
            ax_info.set_title("Stream Overview", loc="left", pad=6)
            ax_info.text(0.02, 0.88, latest_text, va="top", ha="left", family="monospace", fontsize=10, transform=ax_info.transAxes)
            plt.pause(float(cfg.viewer.refresh_s))

    except KeyboardInterrupt:
        LOGGER.info("Stopping on user request")
    finally:
        stream.disconnect()
        plt.close(fig)

    return 0


def _window_from_replay(data: ReplayData, end_index: int, window_samples: int) -> LiveWindow | None:
    end_index = max(0, min(end_index, data.timestamps_s.size))
    if end_index == 0:
        return None
    start_index = max(0, end_index - window_samples)
    return LiveWindow(
        timestamps_s=data.timestamps_s[start_index:end_index],
        device_clock_us=data.device_clock_us[start_index:end_index],
        raw=data.raw[start_index:end_index],
        filtered=data.filtered[start_index:end_index],
    )


def run_replay_mode(cfg: DictConfig, replay_data: ReplayData, reference: OfflineReference, mode: str) -> int:
    window_samples = infer_window_samples(cfg)
    fig, axes, line_raw, line_filtered, line_dt, ax_info = init_figure(cfg)
    _, ax_raw, ax_filtered, ax_dt = axes

    timestamps = replay_data.timestamps_s
    if timestamps.size == 0:
        raise RuntimeError(f"Replay dataset is empty for mode={mode}")

    start_offset_s = max(0.0, float(cfg.replay.start_offset_s))
    replay_speed = max(1e-9, float(cfg.replay.speed))
    loop = bool(cfg.replay.loop)

    LOGGER.info(
        "Replay viewer started: mode=%s source=%s samples=%d window_samples=%d refresh_s=%.3f speed=%.3f loop=%s",
        mode,
        replay_data.source_name,
        timestamps.size,
        window_samples,
        float(cfg.viewer.refresh_s),
        replay_speed,
        loop,
    )

    replay_start_wall = time.monotonic()

    try:
        while plt.fignum_exists(fig.number):
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

            t_rel = window.timestamps_s - window.timestamps_s[-1]
            line_raw.set_data(t_rel, window.raw)
            line_filtered.set_data(t_rel, window.filtered)
            update_axis(ax_raw, t_rel, window.raw)
            update_axis(ax_filtered, t_rel, window.filtered)

            if window.device_clock_us.size >= 2:
                device_dt_ms = np.diff(window.device_clock_us) / 1000.0
                dt_t_rel = t_rel[1:]
                line_dt.set_data(dt_t_rel, device_dt_ms)
                update_axis(ax_dt, dt_t_rel, device_dt_ms)
                observed_rate_hz = 1000.0 / float(np.median(device_dt_ms)) if np.all(device_dt_ms > 0) else float("nan")
                mean_dt_ms = float(np.mean(device_dt_ms))
            else:
                line_dt.set_data([], [])
                observed_rate_hz = float("nan")
                mean_dt_ms = float("nan")

            col_source = (
                f"SOURCE/MODE\n"
                f"name : {replay_data.source_name}\n"
                f"type : {replay_data.source_type}\n"
                f"id   : {replay_data.source_id}\n"
                f"mode : {mode}"
            )
            col_signal = (
                f"SIGNAL ({cfg.viewer.raw_unit_label}/{cfg.viewer.filtered_unit_label})\n"
                f"raw    : {window.raw[-1]:.3f}\n"
                f"filt   : {window.filtered[-1]:.3f}\n"
                f"clock  : {window.device_clock_us[-1]:.0f} us"
            )
            col_replay = (
                f"REPLAY PROGRESS\n"
                f"pos    : {target_index}/{timestamps.size}\n"
                f"time   : {elapsed_s:.2f} s\n"
                f"speed  : {replay_speed:.2f}x"
            )
            col_metrics = (
                f"METRICS\n"
                f"rate   : {observed_rate_hz:.2f} Hz\n"
                f"dt     : {mean_dt_ms:.2f} ms"
            )

            # Helper for side-by-side multiline formatting
            def _zip_cols(*cols):
                sections = [c.split("\n") for c in cols]
                col_widths = [max(len(line) for line in s) + 2 for s in sections]
                max_lines = max(len(s) for s in sections)
                
                for s in sections:
                    while len(s) < max_lines:
                        s.append("")
                        
                rows = []
                for i in range(max_lines):
                    row = ""
                    for j, s_lines in enumerate(sections):
                        w = col_widths[j]
                        row += f"{s_lines[i]:<{w}}"
                    rows.append(row.rstrip())
                return "\n".join(rows)

            latest_text = _zip_cols(col_source, col_signal, col_replay, col_metrics)
            ax_info.clear()
            ax_info.axis("off")
            ax_info.set_xlim(0, 1)
            ax_info.set_ylim(0, 1)
            ax_info.set_title("Stream Overview", loc="left", pad=6)
            ax_info.text(0.02, 0.88, latest_text, va="top", ha="left", family="monospace", fontsize=8, transform=ax_info.transAxes)

            plt.pause(float(cfg.viewer.refresh_s))
            if target_index >= timestamps.size and not loop:
                LOGGER.info("Replay reached the end of the dataset; holding final frame.")
                break

        while plt.fignum_exists(fig.number) and not loop and target_index >= timestamps.size:
            plt.pause(float(cfg.viewer.refresh_s))

    except KeyboardInterrupt:
        LOGGER.info("Stopping on user request")
    finally:
        plt.close(fig)

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
