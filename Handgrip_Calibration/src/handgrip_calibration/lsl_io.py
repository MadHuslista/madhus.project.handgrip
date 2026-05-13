"""LSL stream discovery and CSV recording helpers.

This module is the only place that directly depends on pylsl. All imports are
lazy so offline analysis can run without LSL installed.
"""

from __future__ import annotations

import csv
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .config_schema import StreamConfig
from .export import ensure_dir
from .quality import RateMonitor

log = logging.getLogger(__name__)


@dataclass
class ResolvedStream:
    """Metadata discovered from an LSL stream."""

    name: str
    stream_type: str
    source_id: str
    channel_count: int
    nominal_srate: float
    channel_labels: list[str]


@dataclass
class StreamStats:
    """Live recording counters for one stream."""

    samples: int = 0
    last_timestamp_lsl: float | None = None
    rate_hz: float = 0.0
    max_gap_s: float = 0.0
    channel_labels: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class LSLUnavailableError(RuntimeError):
    """Raised when live LSL operations are requested without pylsl installed."""


def _import_pylsl() -> Any:
    try:
        import pylsl
    except Exception as exc:  # pragma: no cover - depends on optional pylsl
        raise LSLUnavailableError(
            "pylsl is not installed. Install live recording support with: "
            "python -m pip install -e '.[lsl]'"
        ) from exc
    return pylsl


def _labels_from_info(info: Any) -> list[str]:
    """Extract channel labels from an LSL StreamInfo object.

    If the upstream bridge does not publish labels, fallback labels are generated
    as `ch0`, `ch1`, ... so index-based configs still work.
    """

    labels: list[str] = []
    try:
        channels = info.desc().child("channels").child("channel")
        for _ in range(info.channel_count()):
            label = channels.child_value("label") or channels.child_value("name")
            labels.append(label if label else f"ch{len(labels)}")
            channels = channels.next_sibling()
    except Exception as _exc:
        log.debug("Could not parse LSL channel labels (%s); using ch0..chN fallback", _exc)
        labels = []
    if not labels or len(labels) != info.channel_count():
        labels = [f"ch{i}" for i in range(info.channel_count())]
    return labels


def resolve_stream(config: StreamConfig) -> tuple[Any, ResolvedStream]:
    """Resolve one LSL stream based on name/type/source constraints."""

    pylsl = _import_pylsl()
    streams = pylsl.resolve_byprop("name", config.name, timeout=config.timeout_s)
    if not streams and config.stream_type:
        streams = pylsl.resolve_byprop("type", config.stream_type, timeout=config.timeout_s)
    if not streams:
        raise TimeoutError(f"Could not resolve LSL stream {config.name!r} within {config.timeout_s:.1f}s")
    # Prefer exact source_id if configured; otherwise use the first matching stream.
    info = streams[0]
    if config.source_id:
        for candidate in streams:
            if candidate.source_id() == config.source_id:
                info = candidate
                break
    labels = _labels_from_info(info)
    return info, ResolvedStream(
        name=info.name(),
        stream_type=info.type(),
        source_id=info.source_id(),
        channel_count=info.channel_count(),
        nominal_srate=float(info.nominal_srate()),
        channel_labels=labels,
    )


def preflight_streams(streams: dict[str, StreamConfig]) -> dict[str, ResolvedStream]:
    """Resolve all configured LSL streams and return their metadata."""

    resolved: dict[str, ResolvedStream] = {}
    for key, cfg in streams.items():
        try:
            _, meta = resolve_stream(cfg)
            resolved[key] = meta
        except Exception:
            if cfg.required:
                raise
    return resolved


def resolve_channel_indices(labels: list[str], channel_map: dict[str, list[str | int]]) -> dict[str, int]:
    """Resolve canonical channel names to numeric LSL sample indices.

    Each channel map value may contain multiple candidates. String candidates are
    matched against LSL channel labels. Integer candidates are interpreted as
    direct zero-based indices. This lets configs tolerate both current labels and
    future D2/raw-count labels.
    """

    index_by_label = {label: i for i, label in enumerate(labels)}
    resolved: dict[str, int] = {}
    for canonical, candidates in channel_map.items():
        for candidate in candidates:
            if isinstance(candidate, int):
                if 0 <= candidate < len(labels):
                    resolved[canonical] = candidate
                    break
            elif str(candidate) in index_by_label:
                resolved[canonical] = index_by_label[str(candidate)]
                break
    return resolved


class CsvStreamRecorder(threading.Thread):
    """Background thread that records one LSL stream to canonical CSV.

    The writer stores both canonical columns (e.g. `raw`, `clock`) and the raw
    numbered channels. Canonical columns make downstream calibration stable even
    if upstream channel labels are updated later.
    """

    def __init__(
        self,
        *,
        key: str,
        config: StreamConfig,
        output_csv: Path,
        stop_event: threading.Event,
        pull_timeout_s: float = 0.2,
    ) -> None:
        super().__init__(name=f"CsvStreamRecorder[{key}]", daemon=True)
        self.key = key
        self.config = config
        self.output_csv = output_csv
        self.stop_event = stop_event
        self.pull_timeout_s = pull_timeout_s
        self.stats = StreamStats()
        self._inlet = None

    def run(self) -> None:  # pragma: no cover - requires live LSL
        try:
            info, meta = resolve_stream(self.config)
            pylsl = _import_pylsl()
            self._inlet = pylsl.StreamInlet(info, max_buflen=60, recover=True)
            labels = meta.channel_labels
            canonical_indices = resolve_channel_indices(labels, self.config.channel_map)
            self.stats.channel_labels = labels
            ensure_dir(self.output_csv.parent)
            fieldnames = ["timestamp_lsl"] + sorted(canonical_indices.keys()) + [f"channel_{i}" for i in range(len(labels))]
            rate = RateMonitor(window_s=10.0)
            with self.output_csv.open("w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=fieldnames)
                writer.writeheader()
                while not self.stop_event.is_set():
                    sample, timestamp = self._inlet.pull_sample(timeout=self.pull_timeout_s)
                    if sample is None:
                        continue
                    timestamp = float(timestamp)
                    row: dict[str, Any] = {"timestamp_lsl": timestamp}
                    for canonical, idx in canonical_indices.items():
                        row[canonical] = sample[idx]
                    for i, value in enumerate(sample):
                        row[f"channel_{i}"] = value
                    writer.writerow(row)
                    self.stats.samples += 1
                    if self.stats.last_timestamp_lsl is not None:
                        gap = timestamp - self.stats.last_timestamp_lsl
                        if gap > self.stats.max_gap_s:
                            self.stats.max_gap_s = gap
                    self.stats.last_timestamp_lsl = timestamp
                    rate.add(timestamp)
                    self.stats.rate_hz = rate.rate_hz
        except Exception as exc:
            log.error("Stream recorder [%s] failed: %s", self.key, exc)
            self.stats.errors.append(str(exc))


def summarize_stats(stats: Iterable[CsvStreamRecorder]) -> dict[str, dict[str, Any]]:
    """Return JSON-friendly recording stats for a collection of recorders."""

    return {
        recorder.key: {
            "samples": recorder.stats.samples,
            "last_timestamp_lsl": recorder.stats.last_timestamp_lsl,
            "rate_hz": recorder.stats.rate_hz,
            "max_gap_s": recorder.stats.max_gap_s,
            "channel_labels": recorder.stats.channel_labels,
            "errors": recorder.stats.errors,
        }
        for recorder in stats
    }
