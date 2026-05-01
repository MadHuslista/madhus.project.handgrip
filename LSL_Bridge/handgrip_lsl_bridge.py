from __future__ import annotations

import binascii
import csv
import importlib
import json
import logging
import math
import re
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Protocol

import hydra
from hydra.utils import to_absolute_path
from omegaconf import DictConfig, OmegaConf
from pylsl import IRREGULAR_RATE, StreamInfo, StreamOutlet, cf_double64, local_clock
from serial import Serial, SerialException
from serial.tools import list_ports

try:
    import zmq
except Exception:  # pragma: no cover - optional dependency, required only when rs485_ipc.enabled=true
    zmq = None

LOGGER = logging.getLogger("handgrip_lsl_bridge")


class Processor(Protocol):
    def process(self, value: float, sample_time_s: float) -> float:
        ...


@dataclass(slots=True)
class ParsedSample:
    device_clock_us: int
    value: float
    lsl_timestamp: float
    host_unix_time_ns: int
    sequence: Optional[int]
    raw_line: str
    parser_mode: str


@dataclass(slots=True)
class RS485IpcSample:
    seq: Optional[int]
    mode: str
    signal_key: str
    rs485_raw: float
    rs485_clock: float
    host_lsl_ts: float
    host_unix_ts: float
    received_lsl_ts: float
    clock_source: str
    unit_label: str
    status_word: Any
    timestamp_source: str
    configured_frequency_hz: float


class TargetCsvSink:
    FIELDNAMES = [
        "host_unix_time_ns",
        "lsl_timestamp_s",
        "device_clock_us",
        "value_raw",
        "value_filtered",
        "sequence",
        "parser_mode",
        "raw_line",
    ]

    def __init__(self, path: Path, append: bool, flush_every_n_rows: int) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append else "w"
        self._fh = self._path.open(mode, newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._fh, fieldnames=self.FIELDNAMES)
        if (not append) or self._path.stat().st_size == 0:
            self._writer.writeheader()
            self._fh.flush()
        self._flush_every_n_rows = max(1, int(flush_every_n_rows))
        self._rows_since_flush = 0

    def write(self, sample: ParsedSample, filtered_value: float) -> None:
        self._writer.writerow(
            {
                "host_unix_time_ns": sample.host_unix_time_ns,
                "lsl_timestamp_s": f"{sample.lsl_timestamp:.9f}",
                "device_clock_us": sample.device_clock_us,
                "value_raw": repr(sample.value),
                "value_filtered": repr(filtered_value),
                "sequence": "" if sample.sequence is None else sample.sequence,
                "parser_mode": sample.parser_mode,
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
    FIELDNAMES = [
        "host_unix_ts",
        "received_lsl_ts",
        "lsl_timestamp_s",
        "rs485_clock",
        "rs485_raw",
        "rs485_mode",
        "rs485_seq",
        "rs485_signal_key",
        "rs485_clock_source",
        "unit_label",
        "status_word",
        "timestamp_source",
        "configured_frequency_hz",
    ]

    def __init__(self, path: Path, append: bool, flush_every_n_rows: int) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append else "w"
        self._fh = self._path.open(mode, newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._fh, fieldnames=self.FIELDNAMES)
        if (not append) or self._path.stat().st_size == 0:
            self._writer.writeheader()
            self._fh.flush()
        self._flush_every_n_rows = max(1, int(flush_every_n_rows))
        self._rows_since_flush = 0

    def write(self, sample: RS485IpcSample, lsl_timestamp_s: float) -> None:
        self._writer.writerow(
            {
                "host_unix_ts": repr(sample.host_unix_ts),
                "received_lsl_ts": f"{sample.received_lsl_ts:.9f}",
                "lsl_timestamp_s": f"{lsl_timestamp_s:.9f}",
                "rs485_clock": repr(sample.rs485_clock),
                "rs485_raw": repr(sample.rs485_raw),
                "rs485_mode": sample.mode,
                "rs485_seq": "" if sample.seq is None else sample.seq,
                "rs485_signal_key": sample.signal_key,
                "rs485_clock_source": sample.clock_source,
                "unit_label": sample.unit_label,
                "status_word": "" if sample.status_word is None else sample.status_word,
                "timestamp_source": sample.timestamp_source,
                "configured_frequency_hz": "" if not math.isfinite(sample.configured_frequency_hz) else repr(sample.configured_frequency_hz),
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


class LineParser:
    def __init__(self, cfg: DictConfig) -> None:
        self.mode = str(cfg.protocol.mode)
        self.delimiter = str(cfg.protocol.delimiter)
        self.tagged_prefix = str(cfg.protocol.tagged_prefix)
        self.expect_crc16 = bool(cfg.protocol.expect_crc16)
        number = str(cfg.protocol.accepted_numeric_regex)
        self._simple_re = re.compile(
            rf"^\s*(?P<clock>\d+)\s*{re.escape(self.delimiter)}\s*(?P<value>{number})\s*$"
        )
        self._tagged_re = re.compile(
            rf"^\s*(?P<prefix>{re.escape(self.tagged_prefix)})\s*{re.escape(self.delimiter)}\s*"
            rf"(?P<seq>\d+)\s*{re.escape(self.delimiter)}\s*(?P<clock>\d+)\s*{re.escape(self.delimiter)}\s*"
            rf"(?P<value>{number})(?:\s*{re.escape(self.delimiter)}\s*(?P<crc>[0-9A-Fa-f]{{4}}))?\s*$"
        )
        self._legacy_clock: Optional[int] = None
        self._last_seq: Optional[int] = None
        self._parse_errors = 0
        self._log_parse_errors_every_n = max(1, int(cfg.logging.log_parse_errors_every_n))

    def feed(self, raw_line: bytes, arrival_lsl_time: float, arrival_unix_time_ns: int) -> Optional[ParsedSample]:
        line = raw_line.decode("ascii", errors="replace").strip()
        if not line:
            return None

        modes = [self.mode] if self.mode != "auto" else ["tagged_csv", "simple_csv", "legacy_pair_lines"]
        for mode in modes:
            if mode == "tagged_csv":
                sample = self._parse_tagged_csv(line, arrival_lsl_time, arrival_unix_time_ns)
            elif mode == "simple_csv":
                sample = self._parse_simple_csv(line, arrival_lsl_time, arrival_unix_time_ns)
            elif mode == "legacy_pair_lines":
                sample = self._parse_legacy_pair_lines(line, arrival_lsl_time, arrival_unix_time_ns)
            else:
                raise ValueError(f"Unsupported parser mode: {mode}")
            if sample is not None:
                return sample

        self._parse_errors += 1
        if self._parse_errors == 1 or self._parse_errors % self._log_parse_errors_every_n == 0:
            LOGGER.warning("Dropped unparsable line #%d: %r", self._parse_errors, line)
        return None

    def _parse_simple_csv(self, line: str, arrival_lsl_time: float, arrival_unix_time_ns: int) -> Optional[ParsedSample]:
        match = self._simple_re.match(line)
        if not match:
            return None
        return ParsedSample(
            device_clock_us=int(match.group("clock")),
            value=float(match.group("value")),
            lsl_timestamp=arrival_lsl_time,
            host_unix_time_ns=arrival_unix_time_ns,
            sequence=None,
            raw_line=line,
            parser_mode="simple_csv",
        )

    def _parse_tagged_csv(self, line: str, arrival_lsl_time: float, arrival_unix_time_ns: int) -> Optional[ParsedSample]:
        match = self._tagged_re.match(line)
        if not match:
            return None

        seq = int(match.group("seq"))
        clock_us = int(match.group("clock"))
        value = float(match.group("value"))
        crc = match.group("crc")

        if self.expect_crc16:
            if crc is None:
                LOGGER.warning("Dropped tagged frame without CRC16: %r", line)
                return None
            payload = self.delimiter.join([self.tagged_prefix, str(seq), str(clock_us), match.group("value")]).encode(
                "ascii"
            )
            expected_crc = binascii.crc_hqx(payload, 0xFFFF)
            received_crc = int(crc, 16)
            if expected_crc != received_crc:
                LOGGER.warning(
                    "Dropped frame with bad CRC16: expected=%04X received=%04X line=%r",
                    expected_crc,
                    received_crc,
                    line,
                )
                return None

        if self._last_seq is not None and seq != (self._last_seq + 1):
            LOGGER.warning("Target sequence discontinuity detected: last=%d current=%d", self._last_seq, seq)
        self._last_seq = seq

        return ParsedSample(
            device_clock_us=clock_us,
            value=value,
            lsl_timestamp=arrival_lsl_time,
            host_unix_time_ns=arrival_unix_time_ns,
            sequence=seq,
            raw_line=line,
            parser_mode="tagged_csv",
        )

    def _parse_legacy_pair_lines(
        self, line: str, arrival_lsl_time: float, arrival_unix_time_ns: int
    ) -> Optional[ParsedSample]:
        if line.startswith(">read_sample.timestamp:"):
            try:
                self._legacy_clock = int(line.split(":", maxsplit=1)[1])
            except (IndexError, ValueError):
                self._legacy_clock = None
            return None

        if line.startswith(">read_sample.value:"):
            if self._legacy_clock is None:
                LOGGER.warning("Dropped legacy value line without preceding timestamp: %r", line)
                return None
            try:
                value = float(line.split(":", maxsplit=1)[1])
            except (IndexError, ValueError):
                self._legacy_clock = None
                return None
            sample = ParsedSample(
                device_clock_us=self._legacy_clock,
                value=value,
                lsl_timestamp=arrival_lsl_time,
                host_unix_time_ns=arrival_unix_time_ns,
                sequence=None,
                raw_line=line,
                parser_mode="legacy_pair_lines",
            )
            self._legacy_clock = None
            return sample

        return None


class SampleTimeResolver:
    def __init__(self, cfg: DictConfig) -> None:
        self._source = str(cfg.processing.timestamp_source)
        self._last_device_clock_us: int | None = None
        self._last_resolved_time_s: float | None = None

    def resolve(self, sample: ParsedSample) -> float:
        if self._source == "lsl":
            return float(sample.lsl_timestamp)
        if self._source != "device_clock_us":
            raise ValueError(f"Unsupported processing.timestamp_source: {self._source}")

        if self._last_device_clock_us is None:
            self._last_device_clock_us = sample.device_clock_us
            self._last_resolved_time_s = 0.0
            return 0.0

        delta_us = sample.device_clock_us - self._last_device_clock_us
        if delta_us <= 0:
            if delta_us < 0:
                LOGGER.warning(
                    "Non-monotonic target device clock detected: previous=%d current=%d. Resetting processor time base.",
                    self._last_device_clock_us,
                    sample.device_clock_us,
                )
                self._last_resolved_time_s = 0.0
            self._last_device_clock_us = sample.device_clock_us
            return 0.0 if self._last_resolved_time_s is None else self._last_resolved_time_s

        if self._last_resolved_time_s is None:
            self._last_resolved_time_s = 0.0
        self._last_resolved_time_s += delta_us / 1_000_000.0
        self._last_device_clock_us = sample.device_clock_us
        return self._last_resolved_time_s


class TargetTimestampResolver:
    """Map target device timestamps into the LSL clock domain.

    The Arduino/device timestamp remains a diagnostic channel. The returned value
    is passed as the LSL sample timestamp and is therefore the synchronization
    authority used by the viewer/XDF layer.
    """

    def __init__(self, cfg: DictConfig) -> None:
        self._policy = str(cfg.target_timestamping.policy)
        self._max_gap_s = float(cfg.target_timestamping.max_gap_s)
        self._reset_on_nonmonotonic = bool(cfg.target_timestamping.reset_on_nonmonotonic)
        self._anchor_device_us: int | None = None
        self._anchor_lsl_s: float | None = None
        self._last_device_us: int | None = None

    def resolve(self, sample: ParsedSample, arrival_lsl_time: float) -> float:
        if self._policy == "host_receive":
            return arrival_lsl_time
        if self._policy not in {"device_clock_anchor", "device_clock_affine"}:
            raise ValueError(f"Unsupported target_timestamping.policy={self._policy!r}")
        if self._policy == "device_clock_affine":
            # Reserved for a later, explicitly validated timestamp-quality upgrade.
            # The anchor model preserves native device timing without adding a hidden
            # estimator to the calibration path.
            LOGGER.debug("device_clock_affine requested; using device_clock_anchor behavior in this implementation")

        if self._anchor_device_us is None or self._anchor_lsl_s is None:
            self._reset_anchor(sample.device_clock_us, arrival_lsl_time)
            return arrival_lsl_time

        if self._last_device_us is not None:
            delta_s = (sample.device_clock_us - self._last_device_us) / 1_000_000.0
            if sample.device_clock_us < self._last_device_us and self._reset_on_nonmonotonic:
                LOGGER.warning(
                    "Target device clock reset/non-monotonic event: previous=%d current=%d. Re-anchoring to host receive time.",
                    self._last_device_us,
                    sample.device_clock_us,
                )
                self._reset_anchor(sample.device_clock_us, arrival_lsl_time)
                return arrival_lsl_time
            if delta_s > self._max_gap_s:
                LOGGER.warning(
                    "Target device clock gap %.3fs exceeds max_gap_s=%.3fs. Re-anchoring to host receive time.",
                    delta_s,
                    self._max_gap_s,
                )
                self._reset_anchor(sample.device_clock_us, arrival_lsl_time)
                return arrival_lsl_time

        self._last_device_us = sample.device_clock_us
        return self._anchor_lsl_s + (sample.device_clock_us - self._anchor_device_us) / 1_000_000.0

    def _reset_anchor(self, device_clock_us: int, arrival_lsl_time: float) -> None:
        self._anchor_device_us = int(device_clock_us)
        self._anchor_lsl_s = float(arrival_lsl_time)
        self._last_device_us = int(device_clock_us)


class RS485IpcReferencePublisher:
    """Publishes RS485 IPC samples as their own native-rate/reference LSL stream."""

    def __init__(self, cfg: DictConfig, outlet: StreamOutlet | None, sink: ReferenceCsvSink | None) -> None:
        self.cfg = cfg
        self.enabled = bool(cfg.rs485_ipc.enabled) and bool(cfg.streams.reference.enabled)
        self._outlet = outlet
        self._sink = sink
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._context: Any = None
        self._socket: Any = None
        self._last_status_log_monotonic = 0.0
        self._published_count = 0
        self._malformed_count = 0
        self._gap_count = 0
        self._last_seq: Optional[int] = None

    def start(self) -> None:
        if not self.enabled:
            LOGGER.info("Reference RS485 IPC publisher disabled")
            return
        if self._outlet is None:
            raise RuntimeError("Reference stream is enabled but no StreamOutlet was provided")
        if zmq is None:
            raise RuntimeError("rs485_ipc.enabled=true requires pyzmq. Install with: uv add pyzmq")
        self._context = zmq.Context.instance()
        self._socket = self._context.socket(zmq.SUB)
        self._socket.setsockopt(zmq.RCVHWM, int(self.cfg.rs485_ipc.receive_hwm))
        self._socket.setsockopt(zmq.LINGER, 0)
        topic = str(self.cfg.rs485_ipc.topic).encode("utf-8")
        self._socket.setsockopt(zmq.SUBSCRIBE, topic)
        self._socket.connect(str(self.cfg.rs485_ipc.connect))
        self._thread = threading.Thread(target=self._run, name="rs485-reference-lsl-publisher", daemon=True)
        self._thread.start()
        LOGGER.info("Reference IPC publisher connected to %s topic=%s", self.cfg.rs485_ipc.connect, self.cfg.rs485_ipc.topic)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None
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
                payload = parts[-1]
                record = json.loads(payload.decode("utf-8"))
                sample = self._decode_record(record)
            except Exception as exc:
                self._malformed_count += 1
                if self._malformed_count == 1 or self._malformed_count % 100 == 0:
                    LOGGER.warning("Dropped malformed RS485 IPC message #%d: %s", self._malformed_count, exc)
                continue

            if sample.seq is not None:
                if self._last_seq is not None and sample.seq != self._last_seq + 1:
                    self._gap_count += 1
                    if self._gap_count == 1 or self._gap_count % 20 == 0:
                        LOGGER.warning("Reference RS485 sequence gap #%d: last=%s current=%s", self._gap_count, self._last_seq, sample.seq)
                self._last_seq = sample.seq

            timestamp = sample.host_lsl_ts if math.isfinite(sample.host_lsl_ts) else sample.received_lsl_ts
            self._outlet.push_sample(
                [float(sample.rs485_clock), float(sample.rs485_raw)],
                timestamp=timestamp,
                pushthrough=True,
            )
            if self._sink is not None:
                self._sink.write(sample, timestamp)
            self._published_count += 1
            self._log_status_if_due(sample, timestamp)

    def _decode_record(self, record: dict[str, Any]) -> RS485IpcSample:
        schema = str(record.get("schema", ""))
        if schema != "rs485.measurement.v1":
            raise ValueError(f"unsupported schema={schema!r}")
        raw = record.get("rs485_raw")
        clock = record.get("rs485_clock")
        host_lsl_ts = record.get("host_lsl_ts", clock)
        if raw is None or clock is None or host_lsl_ts is None:
            raise ValueError("missing one of rs485_raw, rs485_clock, host_lsl_ts")
        seq_raw = record.get("seq")
        seq = None if seq_raw is None else int(seq_raw)
        configured_frequency_hz = record.get("configured_frequency_hz", math.nan)
        return RS485IpcSample(
            seq=seq,
            mode=str(record.get("mode", "unknown")),
            signal_key=str(record.get("signal_key", "unknown")),
            rs485_raw=float(raw),
            rs485_clock=float(clock),
            host_lsl_ts=float(host_lsl_ts),
            host_unix_ts=float(record.get("host_unix_ts", math.nan)),
            received_lsl_ts=local_clock(),
            clock_source=str(record.get("rs485_clock_source", "unknown")),
            unit_label=str(record.get("unit_label", "")),
            status_word=record.get("status_word"),
            timestamp_source=str(record.get("timestamp_source", "host_lsl_ts")),
            configured_frequency_hz=float(configured_frequency_hz) if configured_frequency_hz is not None else math.nan,
        )

    def _log_status_if_due(self, sample: RS485IpcSample, timestamp: float) -> None:
        now = time.monotonic()
        if self._published_count == 1 or now - self._last_status_log_monotonic >= float(self.cfg.rs485_ipc.log_status_every_s):
            self._last_status_log_monotonic = now
            age_s = local_clock() - timestamp
            LOGGER.info(
                "Reference LSL status: published=%d malformed=%d gaps=%d latest_seq=%s raw=%s clock=%s timestamp_age_s=%.6f mode=%s clock_source=%s",
                self._published_count,
                self._malformed_count,
                self._gap_count,
                sample.seq,
                sample.rs485_raw,
                sample.rs485_clock,
                age_s,
                sample.mode,
                sample.clock_source,
            )


def configure_logging(level_name: str) -> None:
    level = getattr(logging, str(level_name).upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,
    )


def find_port_metadata(port_name: str) -> dict[str, Any]:
    for port in list_ports.comports():
        if port.device == port_name:
            return {
                "device": port.device,
                "serial_number": port.serial_number,
                "manufacturer": port.manufacturer,
                "product": port.product,
                "vid": port.vid,
                "pid": port.pid,
            }
    return {"device": port_name}


def build_target_source_id(cfg: DictConfig, port_meta: dict[str, Any]) -> str:
    explicit = cfg.streams.target.get("source_id")
    if explicit:
        return str(explicit)

    serial_number = port_meta.get("serial_number")
    if serial_number:
        return f"arduino-handgrip-{serial_number}"

    vid = port_meta.get("vid")
    pid = port_meta.get("pid")
    device = str(port_meta.get("device", "unknown")).replace("/", "_")
    if vid is not None and pid is not None:
        return f"arduino-handgrip-{vid:04x}-{pid:04x}-{device}"
    return f"arduino-handgrip-{device}"


def _append_channel(channels: Any, label: str, channel_type: str, unit: str) -> None:
    channel = channels.append_child("channel")
    channel.append_child_value("label", str(label))
    channel.append_child_value("type", str(channel_type))
    channel.append_child_value("unit", str(unit))


def build_target_outlet(cfg: DictConfig, source_id: str) -> StreamOutlet:
    stream_cfg = cfg.streams.target
    info = StreamInfo(
        str(stream_cfg.name),
        str(stream_cfg.type),
        3,
        IRREGULAR_RATE,
        cf_double64,
        source_id,
    )
    desc = info.desc()
    desc.append_child_value("manufacturer", str(stream_cfg.manufacturer))
    desc.append_child_value("device_name", str(stream_cfg.device_name))
    desc.append_child_value("protocol", "arduino_serial_to_lsl")
    desc.append_child_value("sampling_model", "target_native_irregular")
    desc.append_child_value("timestamp_policy", str(cfg.target_timestamping.policy))
    desc.append_child_value("clock_semantics", "LSL sample timestamp is sync authority; device_clock_us channel is diagnostic")
    channels = desc.append_child("channels")
    _append_channel(channels, stream_cfg.channels.device_clock_us.label, stream_cfg.channels.device_clock_us.type, stream_cfg.channels.device_clock_us.unit)
    _append_channel(channels, stream_cfg.channels.raw.label, stream_cfg.channels.raw.type, stream_cfg.channels.raw.unit)
    _append_channel(channels, stream_cfg.channels.filtered.label, stream_cfg.channels.filtered.type, stream_cfg.channels.filtered.unit)
    return StreamOutlet(info, chunk_size=1)


def build_reference_outlet(cfg: DictConfig) -> StreamOutlet:
    stream_cfg = cfg.streams.reference
    source_id = "rs485-reference" if stream_cfg.source_id is None else str(stream_cfg.source_id)
    info = StreamInfo(
        str(stream_cfg.name),
        str(stream_cfg.type),
        2,
        float(stream_cfg.nominal_srate),
        cf_double64,
        source_id,
    )
    desc = info.desc()
    desc.append_child_value("manufacturer", str(stream_cfg.manufacturer))
    desc.append_child_value("device_name", str(stream_cfg.device_name))
    desc.append_child_value("protocol", "rs485_ipc_to_lsl")
    desc.append_child_value("sampling_model", "reference_native_regular")
    desc.append_child_value("rs485_ipc_enabled", str(bool(cfg.rs485_ipc.enabled)))
    desc.append_child_value("rs485_ipc_endpoint", str(cfg.rs485_ipc.connect))
    desc.append_child_value("clock_semantics", "LSL sample timestamp is sync authority; rs485_clock channel is diagnostic")
    channels = desc.append_child("channels")
    _append_channel(channels, stream_cfg.channels.clock.label, stream_cfg.channels.clock.type, stream_cfg.channels.clock.unit)
    _append_channel(channels, stream_cfg.channels.raw.label, stream_cfg.channels.raw.type, stream_cfg.channels.raw.unit)
    return StreamOutlet(info, chunk_size=1)


def build_processor(cfg: DictConfig) -> Processor:
    module_name = str(cfg.processing.module)
    module = importlib.import_module(module_name)
    processor = module.build_processor(cfg.processing)
    if not hasattr(processor, "process"):
        raise TypeError(f"Processing module {module_name!r} returned an object without a process() method")
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
    return TargetCsvSink(
        path=Path(to_absolute_path(str(cfg.csv.target.path))),
        append=bool(cfg.csv.target.append),
        flush_every_n_rows=int(cfg.csv.target.flush_every_n_rows),
    )


def _open_reference_sink(cfg: DictConfig) -> ReferenceCsvSink | None:
    if not bool(cfg.csv.reference.enabled):
        return None
    return ReferenceCsvSink(
        path=Path(to_absolute_path(str(cfg.csv.reference.path))),
        append=bool(cfg.csv.reference.append),
        flush_every_n_rows=int(cfg.csv.reference.flush_every_n_rows),
    )


@hydra.main(version_base=None, config_path="conf", config_name="config")
def app(cfg: DictConfig) -> None:
    configure_logging(str(cfg.logging.level))
    LOGGER.info("Starting two-native-stream bridge with config:\n%s", OmegaConf.to_yaml(cfg))

    target_sink = _open_target_sink(cfg)
    reference_sink = _open_reference_sink(cfg)
    reference_outlet = build_reference_outlet(cfg) if bool(cfg.streams.reference.enabled) else None
    reference_publisher = RS485IpcReferencePublisher(cfg, reference_outlet, reference_sink)
    reference_publisher.start()

    parser = LineParser(cfg)
    processor = build_processor(cfg)
    processor_time_resolver = SampleTimeResolver(cfg)
    target_timestamp_resolver = TargetTimestampResolver(cfg)

    sample_count = 0
    target_outlet: StreamOutlet | None = None
    try:
        while True:
            try:
                LOGGER.info("Opening target serial port %s @ %s baud", cfg.serial.port, cfg.serial.baudrate)
                with Serial(
                    port=str(cfg.serial.port),
                    baudrate=int(cfg.serial.baudrate),
                    timeout=float(cfg.serial.timeout_s),
                ) as ser:
                    settle_serial_input(ser, float(cfg.serial.startup_settle_s))
                    port_meta = find_port_metadata(str(cfg.serial.port))
                    source_id = build_target_source_id(cfg, port_meta)
                    target_outlet = build_target_outlet(cfg, source_id)
                    LOGGER.info(
                        "Target LSL outlet ready: name=%s type=%s source_id=%s csv=%s",
                        cfg.streams.target.name,
                        cfg.streams.target.type,
                        source_id,
                        None if target_sink is None else cfg.csv.target.path,
                    )
                    if reference_outlet is not None:
                        LOGGER.info(
                            "Reference LSL outlet ready: name=%s type=%s source_id=%s nominal_srate=%s csv=%s",
                            cfg.streams.reference.name,
                            cfg.streams.reference.type,
                            cfg.streams.reference.source_id,
                            cfg.streams.reference.nominal_srate,
                            None if reference_sink is None else cfg.csv.reference.path,
                        )

                    while True:
                        raw_line = ser.readline(int(cfg.serial.max_line_bytes) + 1)
                        if not raw_line:
                            continue
                        if len(raw_line) > int(cfg.serial.max_line_bytes) and not raw_line.endswith(b"\n"):
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
                        filtered_value = float(processor.process(sample.value, sample_time_s))

                        target_outlet.push_sample(
                            [float(sample.device_clock_us), float(sample.value), filtered_value],
                            timestamp=sample.lsl_timestamp,
                            pushthrough=True,
                        )
                        if target_sink is not None:
                            target_sink.write(sample, filtered_value)
                        sample_count += 1

                        if sample_count == 1 or sample_count % int(cfg.logging.log_every_n_samples) == 0:
                            LOGGER.info(
                                "Target LSL status: published=%d latest_clock_us=%d raw=%s filtered=%s parser=%s timestamp=%.6f",
                                sample_count,
                                sample.device_clock_us,
                                sample.value,
                                filtered_value,
                                sample.parser_mode,
                                sample.lsl_timestamp,
                            )

            except SerialException as exc:
                LOGGER.exception("Target serial port failure: %s", exc)
                LOGGER.info("Retrying in %.2f s", float(cfg.serial.reconnect_backoff_s))
                time.sleep(float(cfg.serial.reconnect_backoff_s))

    except KeyboardInterrupt:
        LOGGER.info("Stopping on user request")
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
