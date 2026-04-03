from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import hydra
import numpy as np
import pandas as pd
from hydra.utils import to_absolute_path
from matplotlib import pyplot as plt
from omegaconf import DictConfig, OmegaConf
import matplotlib
matplotlib.use('Qt5Agg')
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


EXPECTED_CHANNELS = [
    "device_clock_us",
    "grip_force_raw",
    "grip_force_filtered",
]


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

        desc = info.get("desc", [{}])
        channels = []
        if desc and isinstance(desc, list):
            channels_root = desc[0].get("channels", [{}])
            if channels_root and isinstance(channels_root, list):
                channel_items = channels_root[0].get("channel", [])
                for channel in channel_items:
                    label = _first_scalar(channel.get("label"))
                    if label is not None:
                        channels.append(label)
        LOGGER.info("XDF stream matched: name=%s | labels=%s", name, channels)
        return channels

    LOGGER.warning("No stream named %s found in XDF file %s", expected_stream_name, xdf_path)
    return None


def inspect_xdf_metadata_fallback(xdf_path: Path, expected_stream_name: str) -> list[str] | None:
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


def _first_scalar(value: Any):
    if isinstance(value, list) and value:
        return _first_scalar(value[0])
    return value


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


@hydra.main(version_base=None, config_path="conf", config_name="config")
def app(cfg: DictConfig) -> int:
    configure_logging(str(cfg.logging.level))
    LOGGER.info("Starting viewer with config:\n%s", OmegaConf.to_yaml(cfg, resolve=True))

    window_samples = infer_window_samples(cfg)
    reference = OfflineReference()

    csv_path = _optional_path(cfg.reference.csv_path)
    if csv_path is not None:
        reference.csv_path = csv_path
        reference.csv_columns = inspect_csv(csv_path)

    xdf_path = _optional_path(cfg.reference.xdf_path)
    if xdf_path is not None:
        reference.xdf_path = xdf_path
        reference.xdf_labels = inspect_xdf(xdf_path, str(cfg.stream.name))

    stream = build_stream(cfg)
    validate_live_stream(stream, cfg)

    fig, axes = plt.subplots(3, 1, sharex=True, figsize=(12, 8), constrained_layout=True)
    ax_raw, ax_filtered, ax_dt = axes

    (line_raw,) = ax_raw.plot([], [], label="raw", linewidth=1.0)
    (line_filtered,) = ax_filtered.plot([], [], label="filtered", linewidth=1.2)
    (line_dt,) = ax_dt.plot([], [], label="device dt (ms)", linewidth=1.0)

    ax_raw.set_title("Handgrip raw signal")
    ax_filtered.set_title("Handgrip filtered signal")
    ax_dt.set_title("Device sample interval")
    ax_raw.set_ylabel(str(cfg.viewer.raw_unit_label))
    ax_filtered.set_ylabel(str(cfg.viewer.filtered_unit_label))
    ax_dt.set_ylabel(str(cfg.viewer.dt_unit_label))
    ax_dt.set_xlabel("Relative LSL time (s)")
    ax_raw.grid(True, alpha=0.3)
    ax_filtered.grid(True, alpha=0.3)
    ax_dt.grid(True, alpha=0.3)
    ax_raw.legend(loc="upper left")
    ax_filtered.legend(loc="upper left")
    ax_dt.legend(loc="upper left")

    info_text = fig.text(0.01, 0.99, "", va="top", ha="left", family="monospace")

    LOGGER.info(
        "Viewer started: buffer_samples=%d window_samples=%d refresh_s=%.3f",
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

            latest_text = (
                f"stream={stream.name}  type={stream.stype}  source_id={stream.source_id}\n"
                f"channels={stream.ch_names}\n"
                f"latest raw={live.raw[-1]:.3f} {cfg.viewer.raw_unit_label}   filtered={live.filtered[-1]:.3f} {cfg.viewer.filtered_unit_label}   "
                f"device_clock={live.device_clock_us[-1]:.0f} us\n"
                f"observed_rate≈{observed_rate_hz:.3f} Hz   mean_device_dt≈{mean_dt_ms:.3f} ms   n_new_samples={stream.n_new_samples}\n"
                f"csv_ref={reference.csv_path if reference.csv_path else 'none'}   xdf_ref={reference.xdf_path if reference.xdf_path else 'none'}"
            )
            info_text.set_text(latest_text)
            plt.pause(float(cfg.viewer.refresh_s))

    except KeyboardInterrupt:
        LOGGER.info("Stopping on user request")
    finally:
        stream.disconnect()
        plt.close(fig)

    return 0


if __name__ == "__main__":
    raise SystemExit(app())
