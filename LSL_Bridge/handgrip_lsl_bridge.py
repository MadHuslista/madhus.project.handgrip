"""Calibration-schema LSL bridge for the Handgrip system.

This is a breaking upgrade that removes the legacy single-value Arduino parser
and the historical fused/unified stream. The bridge publishes exactly the two
native streams consumed by the Handgrip_Calibration module:

* HandgripTarget: irregular Arduino/HX711 D2 frames.
* HandgripReference: regular-ish RS485 acquisition-board IPC frames.

The bridge also emits an operational marker stream, HandgripComponentEvents, for
component-level events such as target metadata, serial reconnects, and IPC gaps.
Calibration-trial markers remain owned by the Handgrip_Calibration recorder.
"""

from __future__ import annotations

import csv
import importlib
import json
import logging
import math
import re
import sys
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional, Protocol

import hydra
from hydra.utils import to_absolute_path
from omegaconf import DictConfig, OmegaConf
from pylsl import IRREGULAR_RATE, StreamInfo, StreamOutlet, cf_double64, cf_string, local_clock
from serial import Serial, SerialException
from serial.tools import list_ports

try:
    import zmq
except Exception:  # pragma: no cover - optional runtime dependency
    zmq = None

LOGGER = logging.getLogger("handgrip_lsl_bridge")


class Processor(Protocol):
    """Small protocol implemented by filter.py processors."""

    def process(self, value: float, sample_time_s: float) -> float:
        ...


@dataclass(slots=True)
class FirmwareMetadata:
    """Metadata reported by the target firmware M2 boot frame."""

    payload_schema: int | None = None
    firmware_version: str | None = None
    git_sha: str | None = None
    hx711_rate_hz: float | None = None
    scale_factor: float | None = None
    scale_offset: float | None = None
    unit: str | None = None
    last_seen_lsl_ts: float | None = None


@dataclass(slots=True)
class ParsedTargetSample:
    """Canonical target sample parsed from a strict D2 UART line."""

    sequence: int
    device_clock_us: int
    target_raw_count: float
    target_current_units: float
    target_status: int
    lsl_timestamp: float
    host_unix_time_ns: int
    raw_line: str


@dataclass(slots=True)
class ReferenceSample:
    """Canonical reference sample decoded from RS485_GUI IPC."""

    sequence: int
    mode: str
    signal_key: str
    reference_force_N: float
    reference_clock_s: float
    host_lsl_ts: float
    host_unix_ts: float
    received_lsl_ts: float
    clock_source: str
    unit_label: str
    status: int
    timestamp_source: str
    configured_frequency_hz: float
    session_id: str | None = None
    board_profile: dict[str, Any] = field(default_factory=dict)


class ComponentEventOutlet:
    """Operational marker stream for diagnostics and session manifests.

    This stream is intentionally separate from HandgripCalibrationMarkers. The
    calibration recorder owns trial markers; the bridge only reports component
    state transitions that help audit a recording after the fact.
    """

    def __init__(self, cfg: DictConfig) -> None:
        self.enabled = bool(cfg.component_events.enabled)
        self._outlet: StreamOutlet | None = None
        if not self.enabled:
            return
        info = StreamInfo(
            str(cfg.component_events.name),
            str(cfg.component_events.type),
            1,
            IRREGULAR_RATE,
            cf_string,
            str(cfg.component_events.source_id),
        )
        desc = info.desc()
        desc.append_child_value("schema", "handgrip_component_event.v1")
        desc.append_child_value("producer", "LSL_Bridge")
        self._outlet = StreamOutlet(info, chunk_size=1)

    def emit(self, event: str, **payload: Any) -> None:
        if self._outlet is None:
            return
        record = {
            "schema": "handgrip_component_event.v1",
            "producer": "LSL_Bridge",
            "event": event,
            "host_unix_ns": time.time_ns(),
            "lsl_ts": local_clock(),
            **payload,
        }
        self._outlet.push_sample([json.dumps(record, separators=(",", ":"), ensure_ascii=False)], pushthrough=True)


class TargetCsvSink:
    """Writes the exact target samples published to LSL into CSV."""

    FIELDNAMES = [
        "host_unix_time_ns",
        "lsl_timestamp_s",
        "seq",
        "device_clock_us",
        "target_raw_count",
        "target_current_units",
        "target_filtered_units",
        "target_status",
        "raw_line",
    ]

    def __init__(self, path: Path, append: bool, flush_every_n_rows: int) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self._path.open("a" if append else "w", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._fh, fieldnames=self.FIELDNAMES)
        if (not append) or self._path.stat().st_size == 0:
            self._writer.writeheader()
        self._flush_every_n_rows = max(1, int(flush_every_n_rows))
        self._rows_since_flush = 0

    def write(self, sample: ParsedTargetSample, filtered_units: float) -> None:
        self._writer.writerow(
            {
                "host_unix_time_ns": sample.host_unix_time_ns,
                "lsl_timestamp_s": f"{sample.lsl_timestamp:.9f}",
                "seq": sample.sequence,
                "device_clock_us": sample.device_clock_us,
                "target_raw_count": repr(sample.target_raw_count),
                "target_current_units": repr(sample.target_current_units),
                "target_filtered_units": repr(filtered_units),
                "target_status": sample.target_status,
                "raw_line": sample.raw_line,
            }
        )
        self._rows_since_flush += 1
        if self._rows_since_flush >= self._flush_every_n_rows:
            self._fh.flush()
            self._rows_since_flush = 0

    def close(self) -> None:
        try:
            self._fh.flush()
        finally:
            self._fh.close()


class ReferenceCsvSink:
    """Writes canonical reference samples published to LSL into CSV."""

    FIELDNAMES = [
        "host_unix_ts",
        "received_lsl_ts",
        "lsl_timestamp_s",
        "seq",
        "reference_clock_s",
        "reference_force_N",
        "reference_status",
        "rs485_mode",
        "rs485_signal_key",
        "rs485_clock_source",
        "unit_label",
        "timestamp_source",
        "configured_frequency_hz",
        "session_id",
    ]

    def __init__(self, path: Path, append: bool, flush_every_n_rows: int) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self._path.open("a" if append else "w", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._fh, fieldnames=self.FIELDNAMES)
        if (not append) or self._path.stat().st_size == 0:
            self._writer.writeheader()
        self._flush_every_n_rows = max(1, int(flush_every_n_rows))
        self._rows_since_flush = 0

    def write(self, sample: ReferenceSample, lsl_timestamp_s: float) -> None:
        self._writer.writerow(
            {
                "host_unix_ts": repr(sample.host_unix_ts),
                "received_lsl_ts": f"{sample.received_lsl_ts:.9f}",
                "lsl_timestamp_s": f"{lsl_timestamp_s:.9f}",
                "seq": sample.sequence,
                "reference_clock_s": repr(sample.reference_clock_s),
                "reference_force_N": repr(sample.reference_force_N),
                "reference_status": sample.status,
                "rs485_mode": sample.mode,
                "rs485_signal_key": sample.signal_key,
                "rs485_clock_source": sample.clock_source,
                "unit_label": sample.unit_label,
                "timestamp_source": sample.timestamp_source,
                "configured_frequency_hz": "" if not math.isfinite(sample.configured_frequency_hz) else repr(sample.configured_frequency_hz),
                "session_id": sample.session_id or "",
            }
        )
        self._rows_since_flush += 1
        if self._rows_since_flush >= self._flush_every_n_rows:
            self._fh.flush()
            self._rows_since_flush = 0

    def close(self) -> None:
        try:
            self._fh.flush()
        finally:
            self._fh.close()


class D2LineParser:
    """Strict parser for the target firmware D2/M2 serial protocol."""

    def __init__(self, cfg: DictConfig, events: ComponentEventOutlet) -> None:
        self.delimiter = str(cfg.protocol.delimiter)
        self.data_prefix = str(cfg.protocol.data_prefix)
        self.metadata_prefix = str(cfg.protocol.metadata_prefix)
        number = str(cfg.protocol.accepted_numeric_regex)
        self._data_re = re.compile(
            rf"^\s*{re.escape(self.data_prefix)}{re.escape(self.delimiter)}"
            rf"(?P<seq>\d+){re.escape(self.delimiter)}"
            rf"(?P<clock>\d+){re.escape(self.delimiter)}"
            rf"(?P<raw>{number}){re.escape(self.delimiter)}"
            rf"(?P<units>{number}){re.escape(self.delimiter)}"
            rf"(?P<status>\d+)\s*$"
        )
        self._last_seq: int | None = None
        self._parse_errors = 0
        self._metadata = FirmwareMetadata()
        self._events = events
        self._log_parse_errors_every_n = max(1, int(cfg.logging.log_parse_errors_every_n))

    @property
    def metadata(self) -> FirmwareMetadata:
        return self._metadata

    def feed(self, raw_line: bytes, arrival_lsl_time: float, arrival_unix_time_ns: int) -> ParsedTargetSample | None:
        line = raw_line.decode("ascii", errors="replace").strip()
        if not line:
            return None
        if line.startswith(f"{self.metadata_prefix}{self.delimiter}"):
            self._parse_metadata(line, arrival_lsl_time)
            return None
        match = self._data_re.match(line)
        if not match:
            self._parse_errors += 1
            if self._parse_errors == 1 or self._parse_errors % self._log_parse_errors_every_n == 0:
                LOGGER.warning("Dropped non-D2 target line #%d: %r", self._parse_errors, line)
            return None
        seq = int(match.group("seq"))
        if self._last_seq is not None and seq != self._last_seq + 1:
            self._events.emit("target_sequence_gap", last_seq=self._last_seq, current_seq=seq)
            LOGGER.warning("Target sequence discontinuity detected: last=%d current=%d", self._last_seq, seq)
        self._last_seq = seq
        return ParsedTargetSample(
            sequence=seq,
            device_clock_us=int(match.group("clock")),
            target_raw_count=float(match.group("raw")),
            target_current_units=float(match.group("units")),
            target_status=int(match.group("status")),
            lsl_timestamp=arrival_lsl_time,
            host_unix_time_ns=arrival_unix_time_ns,
            raw_line=line,
        )

    def _parse_metadata(self, line: str, arrival_lsl_time: float) -> None:
        parts = line.split(self.delimiter)
        if len(parts) < 8:
            LOGGER.warning("Malformed M2 metadata line: %r", line)
            return
        try:
            self._metadata = FirmwareMetadata(
                payload_schema=int(parts[1]),
                firmware_version=parts[2],
                git_sha=parts[3],
                hx711_rate_hz=float(parts[4]),
                scale_factor=float(parts[5]),
                scale_offset=float(parts[6]),
                unit=parts[7],
                last_seen_lsl_ts=arrival_lsl_time,
            )
        except ValueError as exc:
            LOGGER.warning("Could not decode M2 metadata line %r: %s", line, exc)
            return
        self._events.emit("target_metadata", **asdict(self._metadata))
        LOGGER.info("Target metadata received: %s", self._metadata)


class SampleTimeResolver:
    """Resolve filter-time from either LSL timestamps or device-clock deltas."""

    def __init__(self, cfg: DictConfig) -> None:
        self._source = str(cfg.processing.timestamp_source)
        self._last_device_clock_us: int | None = None
        self._last_resolved_time_s: float = 0.0

    def resolve(self, sample: ParsedTargetSample) -> float:
        if self._source == "lsl":
            return float(sample.lsl_timestamp)
        if self._source != "device_clock_us":
            raise ValueError(f"Unsupported processing.timestamp_source={self._source!r}")
        if self._last_device_clock_us is None:
            self._last_device_clock_us = sample.device_clock_us
            self._last_resolved_time_s = 0.0
            return 0.0
        delta_us = sample.device_clock_us - self._last_device_clock_us
        if delta_us > 0:
            self._last_resolved_time_s += delta_us / 1_000_000.0
        self._last_device_clock_us = sample.device_clock_us
        return self._last_resolved_time_s


class TargetTimestampResolver:
    """Map target device timestamps into the LSL clock domain."""

    def __init__(self, cfg: DictConfig, events: ComponentEventOutlet) -> None:
        self._policy = str(cfg.target_timestamping.policy)
        self._max_gap_s = float(cfg.target_timestamping.max_gap_s)
        self._reset_on_nonmonotonic = bool(cfg.target_timestamping.reset_on_nonmonotonic)
        self._anchor_device_us: int | None = None
        self._anchor_lsl_s: float | None = None
        self._last_device_us: int | None = None
        self._events = events

    def resolve(self, sample: ParsedTargetSample, arrival_lsl_time: float) -> float:
        if self._policy == "host_receive":
            return arrival_lsl_time
        if self._policy != "device_clock_anchor":
            raise ValueError("Only target_timestamping.policy=host_receive|device_clock_anchor is supported in schema v2")
        if self._anchor_device_us is None or self._anchor_lsl_s is None:
            self._reset_anchor(sample.device_clock_us, arrival_lsl_time, reason="initial_anchor")
            return arrival_lsl_time
        if self._last_device_us is not None:
            delta_s = (sample.device_clock_us - self._last_device_us) / 1_000_000.0
            if sample.device_clock_us < self._last_device_us and self._reset_on_nonmonotonic:
                self._reset_anchor(sample.device_clock_us, arrival_lsl_time, reason="nonmonotonic_device_clock")
                return arrival_lsl_time
            if delta_s > self._max_gap_s:
                self._reset_anchor(sample.device_clock_us, arrival_lsl_time, reason="device_clock_gap", gap_s=delta_s)
                return arrival_lsl_time
        self._last_device_us = sample.device_clock_us
        return self._anchor_lsl_s + (sample.device_clock_us - self._anchor_device_us) / 1_000_000.0

    def _reset_anchor(self, device_clock_us: int, arrival_lsl_time: float, *, reason: str, **payload: Any) -> None:
        self._anchor_device_us = int(device_clock_us)
        self._anchor_lsl_s = float(arrival_lsl_time)
        self._last_device_us = int(device_clock_us)
        self._events.emit("target_timestamp_anchor_reset", reason=reason, device_clock_us=device_clock_us, **payload)


def configure_logging(level_name: str) -> None:
    level = getattr(logging, str(level_name).upper(), logging.INFO)
    logging.basicConfig(level=level, format="[%(asctime)s][%(name)s][%(levelname)s] - %(message)s")


def find_port_metadata(port_name: str) -> dict[str, Any]:
    for port in list_ports.comports():
        if port.device == port_name:
            return {
                "device": port.device,
                "description": port.description,
                "hwid": port.hwid,
                "vid": port.vid,
                "pid": port.pid,
                "serial_number": getattr(port, "serial_number", None),
                "manufacturer": getattr(port, "manufacturer", None),
                "product": getattr(port, "product", None),
            }
    return {"device": port_name}


def build_target_source_id(cfg: DictConfig, port_meta: dict[str, Any]) -> str:
    explicit = cfg.streams.target.get("source_id")
    if explicit:
        return str(explicit)
    serial_number = port_meta.get("serial_number")
    if serial_number:
        return f"arduino-handgrip-{serial_number}"
    device = str(port_meta.get("device", "unknown")).replace("/", "_")
    return f"arduino-handgrip-{device}"


def _append_channel(channels: Any, label: str, channel_type: str, unit: str) -> None:
    channel = channels.append_child("channel")
    channel.append_child_value("label", str(label))
    channel.append_child_value("type", str(channel_type))
    channel.append_child_value("unit", str(unit))


def _append_metadata(desc: Any, metadata: dict[str, Any]) -> None:
    for key, value in metadata.items():
        if value is not None:
            desc.append_child_value(str(key), str(value))


def build_target_outlet(cfg: DictConfig, source_id: str) -> StreamOutlet:
    stream_cfg = cfg.streams.target
    info = StreamInfo(str(stream_cfg.name), str(stream_cfg.type), 6, IRREGULAR_RATE, cf_double64, source_id)
    desc = info.desc()
    _append_metadata(
        desc,
        {
            "schema": "handgrip_target_stream.v2",
            "session_id": cfg.session.get("session_id"),
            "manufacturer": stream_cfg.manufacturer,
            "device_name": stream_cfg.device_name,
            "payload_schema": stream_cfg.payload_schema,
            "sampling_model": "target_native_irregular",
            "timestamp_policy": cfg.target_timestamping.policy,
            "clock_semantics": "LSL timestamp is synchronization authority; device_clock_us is diagnostic",
            "fit_signal": "target_raw_count",
        },
    )
    channels = desc.append_child("channels")
    for channel_key in ["seq", "device_clock_us", "raw_count", "current_units", "filtered_units", "status"]:
        c = stream_cfg.channels[channel_key]
        _append_channel(channels, c.label, c.type, c.unit)
    return StreamOutlet(info, chunk_size=1)


def build_reference_outlet(cfg: DictConfig) -> StreamOutlet:
    stream_cfg = cfg.streams.reference
    source_id = "rs485-reference" if stream_cfg.source_id is None else str(stream_cfg.source_id)
    info = StreamInfo(str(stream_cfg.name), str(stream_cfg.type), 4, float(stream_cfg.nominal_srate), cf_double64, source_id)
    desc = info.desc()
    _append_metadata(
        desc,
        {
            "schema": "handgrip_reference_stream.v2",
            "session_id": cfg.session.get("session_id"),
            "manufacturer": stream_cfg.manufacturer,
            "device_name": stream_cfg.device_name,
            "sampling_model": "reference_native_regular",
            "nominal_srate_hz": stream_cfg.nominal_srate,
            "rs485_ipc_endpoint": cfg.rs485_ipc.connect,
            "clock_semantics": "LSL timestamp is synchronization authority; reference_clock_s is diagnostic",
            "fit_signal": "reference_force_N",
        },
    )
    channels = desc.append_child("channels")
    for channel_key in ["seq", "clock", "force", "status"]:
        c = stream_cfg.channels[channel_key]
        _append_channel(channels, c.label, c.type, c.unit)
    return StreamOutlet(info, chunk_size=1)


def build_processor(cfg: DictConfig) -> Processor:
    module = importlib.import_module(str(cfg.processing.module))
    processor = module.build_processor(cfg.processing)
    if not hasattr(processor, "process"):
        raise TypeError("processing module returned an object without process()")
    return processor


def settle_serial_input(ser: Serial, startup_settle_s: float) -> None:
    ser.reset_input_buffer()
    deadline = time.monotonic() + max(0.0, startup_settle_s)
    while time.monotonic() < deadline:
        ser.readline()
    ser.reset_input_buffer()


def _open_target_sink(cfg: DictConfig) -> TargetCsvSink | None:
    if not bool(cfg.csv.target.enabled):
        return None
    return TargetCsvSink(Path(to_absolute_path(str(cfg.csv.target.path))), bool(cfg.csv.target.append), int(cfg.csv.target.flush_every_n_rows))


def _open_reference_sink(cfg: DictConfig) -> ReferenceCsvSink | None:
    if not bool(cfg.csv.reference.enabled):
        return None
    return ReferenceCsvSink(Path(to_absolute_path(str(cfg.csv.reference.path))), bool(cfg.csv.reference.append), int(cfg.csv.reference.flush_every_n_rows))


class RS485IpcReferencePublisher:
    """Subscribes to RS485_GUI IPC and republishes canonical reference LSL."""

    def __init__(self, cfg: DictConfig, outlet: StreamOutlet | None, sink: ReferenceCsvSink | None, events: ComponentEventOutlet) -> None:
        self.cfg = cfg
        self.enabled = bool(cfg.rs485_ipc.enabled) and bool(cfg.streams.reference.enabled)
        self._outlet = outlet
        self._sink = sink
        self._events = events
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._context: Any = None
        self._socket: Any = None
        self._last_status_log_monotonic = 0.0
        self._published_count = 0
        self._malformed_count = 0
        self._gap_count = 0
        self._last_seq: int | None = None

    def start(self) -> None:
        if not self.enabled:
            LOGGER.info("Reference RS485 IPC publisher disabled")
            return
        if self._outlet is None:
            raise RuntimeError("Reference stream enabled but no StreamOutlet was provided")
        if zmq is None:
            raise RuntimeError("rs485_ipc.enabled=true requires pyzmq")
        self._context = zmq.Context.instance()
        self._socket = self._context.socket(zmq.SUB)
        self._socket.setsockopt(zmq.RCVHWM, int(self.cfg.rs485_ipc.receive_hwm))
        self._socket.setsockopt(zmq.LINGER, 0)
        topic = str(self.cfg.rs485_ipc.topic).encode("utf-8")
        self._socket.setsockopt(zmq.SUBSCRIBE, topic)
        self._socket.connect(str(self.cfg.rs485_ipc.connect))
        self._thread = threading.Thread(target=self._run, name="rs485-reference-lsl-publisher", daemon=True)
        self._thread.start()
        self._events.emit("reference_ipc_connected", endpoint=str(self.cfg.rs485_ipc.connect), topic=str(self.cfg.rs485_ipc.topic))
        LOGGER.info("Reference IPC publisher connected to %s topic=%s", self.cfg.rs485_ipc.connect, self.cfg.rs485_ipc.topic)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        if self._socket is not None:
            try:
                self._socket.close(0)
            except Exception:
                pass
        self._socket = None

    def _run(self) -> None:
        assert self._socket is not None
        assert self._outlet is not None
        while not self._stop_event.is_set():
            try:
                parts = self._socket.recv_multipart(flags=zmq.NOBLOCK)
            except zmq.Again:
                time.sleep(0.001)
                continue
            except Exception as exc:
                LOGGER.warning("Reference IPC receive warning: %s", exc)
                time.sleep(0.05)
                continue
            try:
                record = json.loads(parts[-1].decode("utf-8"))
                sample = self._decode_record(record)
            except Exception as exc:
                self._malformed_count += 1
                if self._malformed_count == 1 or self._malformed_count % 100 == 0:
                    self._events.emit("reference_ipc_malformed", count=self._malformed_count, error=str(exc))
                    LOGGER.warning("Dropped malformed RS485 IPC message #%d: %s", self._malformed_count, exc)
                continue
            if sample.sequence >= 0:
                if self._last_seq is not None and sample.sequence != self._last_seq + 1:
                    self._gap_count += 1
                    self._events.emit("reference_sequence_gap", last_seq=self._last_seq, current_seq=sample.sequence, count=self._gap_count)
                    LOGGER.warning("Reference RS485 sequence gap #%d: last=%s current=%s", self._gap_count, self._last_seq, sample.sequence)
                self._last_seq = sample.sequence
            timestamp = sample.host_lsl_ts if math.isfinite(sample.host_lsl_ts) else sample.received_lsl_ts
            self._outlet.push_sample(
                [float(sample.sequence), float(sample.reference_clock_s), float(sample.reference_force_N), float(sample.status)],
                timestamp=timestamp,
                pushthrough=True,
            )
            if self._sink is not None:
                self._sink.write(sample, timestamp)
            self._published_count += 1
            self._log_status_if_due(sample, timestamp)

    def _decode_record(self, record: dict[str, Any]) -> ReferenceSample:
        if str(record.get("schema", "")) != "rs485.measurement.v1":
            raise ValueError(f"unsupported schema={record.get('schema')!r}")
        force = record.get("reference_force_N", record.get("rs485_raw"))
        clock = record.get("reference_clock_s", record.get("rs485_clock"))
        host_lsl_ts = record.get("host_lsl_ts", clock)
        if force is None or clock is None or host_lsl_ts is None:
            raise ValueError("missing force/clock/host_lsl_ts")
        status_raw = record.get("reference_status", record.get("status_word", 0))
        if isinstance(status_raw, str):
            try:
                status = int(status_raw, 0)
            except ValueError:
                status = 0
        else:
            status = 0 if status_raw is None else int(status_raw)
        seq_raw = record.get("seq", -1)
        configured_frequency_hz = record.get("configured_frequency_hz", math.nan)
        return ReferenceSample(
            sequence=int(seq_raw) if seq_raw is not None else -1,
            mode=str(record.get("mode", "unknown")),
            signal_key=str(record.get("signal_key", "reference_force_N")),
            reference_force_N=float(force),
            reference_clock_s=float(clock),
            host_lsl_ts=float(host_lsl_ts),
            host_unix_ts=float(record.get("host_unix_ts", math.nan)),
            received_lsl_ts=local_clock(),
            clock_source=str(record.get("rs485_clock_source", record.get("clock_source", "unknown"))),
            unit_label=str(record.get("unit_label", "N")),
            status=status,
            timestamp_source=str(record.get("timestamp_source", "host_lsl_ts")),
            configured_frequency_hz=float(configured_frequency_hz) if configured_frequency_hz is not None else math.nan,
            session_id=record.get("session_id"),
            board_profile=record.get("board_profile", {}) or {},
        )

    def _log_status_if_due(self, sample: ReferenceSample, timestamp: float) -> None:
        now = time.monotonic()
        if self._published_count == 1 or now - self._last_status_log_monotonic >= float(self.cfg.rs485_ipc.log_status_every_s):
            self._last_status_log_monotonic = now
            LOGGER.info(
                "Reference LSL status: published=%d malformed=%d gaps=%d latest_seq=%s force_N=%s timestamp_age_s=%.6f mode=%s",
                self._published_count,
                self._malformed_count,
                self._gap_count,
                sample.sequence,
                sample.reference_force_N,
                local_clock() - timestamp,
                sample.mode,
            )


@hydra.main(version_base=None, config_path="conf", config_name="config")
def app(cfg: DictConfig) -> None:
    configure_logging(str(cfg.logging.level))
    LOGGER.info("Starting calibration-schema LSL bridge with config:\n%s", OmegaConf.to_yaml(cfg))
    events = ComponentEventOutlet(cfg)
    events.emit("bridge_start", config_schema=str(cfg.schema.version), session_id=cfg.session.get("session_id"))

    target_sink = _open_target_sink(cfg)
    reference_sink = _open_reference_sink(cfg)
    reference_outlet = build_reference_outlet(cfg) if bool(cfg.streams.reference.enabled) else None
    reference_publisher = RS485IpcReferencePublisher(cfg, reference_outlet, reference_sink, events)
    reference_publisher.start()

    parser = D2LineParser(cfg, events)
    processor = build_processor(cfg)
    processor_time_resolver = SampleTimeResolver(cfg)
    target_timestamp_resolver = TargetTimestampResolver(cfg, events)
    sample_count = 0

    try:
        while True:
            try:
                LOGGER.info("Opening target serial port %s @ %s baud", cfg.serial.port, cfg.serial.baudrate)
                with Serial(port=str(cfg.serial.port), baudrate=int(cfg.serial.baudrate), timeout=float(cfg.serial.timeout_s)) as ser:
                    settle_serial_input(ser, float(cfg.serial.startup_settle_s))
                    port_meta = find_port_metadata(str(cfg.serial.port))
                    source_id = build_target_source_id(cfg, port_meta)
                    target_outlet = build_target_outlet(cfg, source_id)
                    events.emit("target_serial_connected", port=str(cfg.serial.port), baudrate=int(cfg.serial.baudrate), source_id=source_id, port_metadata=port_meta)
                    LOGGER.info("Target LSL outlet ready: name=%s source_id=%s", cfg.streams.target.name, source_id)
                    while True:
                        raw_line = ser.readline(int(cfg.serial.max_line_bytes) + 1)
                        if not raw_line:
                            continue
                        if len(raw_line) > int(cfg.serial.max_line_bytes) and not raw_line.endswith(b"\n"):
                            events.emit("target_overlong_line")
                            LOGGER.warning("Dropped overlong target serial line; flushing input buffer")
                            ser.reset_input_buffer()
                            continue
                        arrival_unix_time_ns = time.time_ns()
                        arrival_lsl_time = local_clock() - float(cfg.serial.transport_latency_s)
                        sample = parser.feed(raw_line, arrival_lsl_time, arrival_unix_time_ns)
                        if sample is None:
                            continue
                        sample.lsl_timestamp = target_timestamp_resolver.resolve(sample, arrival_lsl_time)
                        sample_time_s = processor_time_resolver.resolve(sample)
                        filtered_units = float(processor.process(sample.target_current_units, sample_time_s))
                        target_outlet.push_sample(
                            [
                                float(sample.sequence),
                                float(sample.device_clock_us),
                                float(sample.target_raw_count),
                                float(sample.target_current_units),
                                filtered_units,
                                float(sample.target_status),
                            ],
                            timestamp=sample.lsl_timestamp,
                            pushthrough=True,
                        )
                        if target_sink is not None:
                            target_sink.write(sample, filtered_units)
                        sample_count += 1
                        if sample_count == 1 or sample_count % int(cfg.logging.log_every_n_samples) == 0:
                            LOGGER.info(
                                "Target LSL status: published=%d seq=%d clock_us=%d raw_count=%s current_units=%s status=%d timestamp=%.6f",
                                sample_count,
                                sample.sequence,
                                sample.device_clock_us,
                                sample.target_raw_count,
                                sample.target_current_units,
                                sample.target_status,
                                sample.lsl_timestamp,
                            )
            except SerialException as exc:
                events.emit("target_serial_error", error=str(exc))
                LOGGER.exception("Target serial port failure: %s", exc)
                time.sleep(float(cfg.serial.reconnect_backoff_s))
    except KeyboardInterrupt:
        LOGGER.info("Stopping on user request")
        events.emit("bridge_stop", reason="keyboard_interrupt")
    finally:
        reference_publisher.stop()
        if target_sink is not None:
            target_sink.close()
        if reference_sink is not None:
            reference_sink.close()


def main() -> int:
    try:
        app()
        return 0
    except Exception:
        LOGGER.exception("Fatal error in bridge")
        return 1


if __name__ == "__main__":
    sys.exit(main())
