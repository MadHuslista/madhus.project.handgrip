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
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Deque, Optional, Protocol

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


@dataclass(slots=True)
class RS485Selection:
    sample: Optional[RS485IpcSample]
    age_s: float
    missing_reason: str


class CsvSink:
    FIELDNAMES = [
        "host_unix_time_ns",
        "lsl_timestamp_s",
        "device_clock_us",
        "value_raw",
        "value_filtered",
        "rs485_raw",
        "rs485_clock",
        "rs485_mode",
        "rs485_seq",
        "rs485_signal_key",
        "rs485_host_lsl_ts",
        "rs485_clock_source",
        "rs485_age_s",
        "rs485_missing_reason",
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

    def write(self, sample: ParsedSample, filtered_value: float, rs485_selection: Optional[RS485Selection] = None) -> None:
        rs485 = rs485_selection.sample if rs485_selection is not None else None
        self._writer.writerow(
            {
                "host_unix_time_ns": sample.host_unix_time_ns,
                "lsl_timestamp_s": f"{sample.lsl_timestamp:.9f}",
                "device_clock_us": sample.device_clock_us,
                "value_raw": repr(sample.value),
                "value_filtered": repr(filtered_value),
                "rs485_raw": "" if rs485 is None else repr(rs485.rs485_raw),
                "rs485_clock": "" if rs485 is None else repr(rs485.rs485_clock),
                "rs485_mode": "" if rs485 is None else rs485.mode,
                "rs485_seq": "" if rs485 is None or rs485.seq is None else rs485.seq,
                "rs485_signal_key": "" if rs485 is None else rs485.signal_key,
                "rs485_host_lsl_ts": "" if rs485 is None else f"{rs485.host_lsl_ts:.9f}",
                "rs485_clock_source": "" if rs485 is None else rs485.clock_source,
                "rs485_age_s": "" if rs485_selection is None else f"{rs485_selection.age_s:.9f}",
                "rs485_missing_reason": "" if rs485_selection is None else rs485_selection.missing_reason,
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
            LOGGER.warning("Sequence discontinuity detected: last=%d current=%d", self._last_seq, seq)
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
                    "Non-monotonic device clock detected: previous=%d current=%d. Resetting processor time base.",
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



class RS485IpcSubscriber:
    """Best-effort local IPC subscriber for RS485 MeasurementFrame data."""

    def __init__(self, cfg: DictConfig) -> None:
        self.cfg = cfg
        self.enabled = bool(cfg.rs485_ipc.enabled)
        self._buffer: Deque[RS485IpcSample] = deque(maxlen=max(1, int(cfg.rs485_ipc.buffer_max_frames)))
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._context: Any = None
        self._socket: Any = None
        self._last_status_log_monotonic = 0.0
        self._received_count = 0
        self._malformed_count = 0
        self._gap_count = 0
        self._last_seq: Optional[int] = None
        self._last_valid: Optional[RS485IpcSample] = None

    def start(self) -> None:
        if not self.enabled:
            LOGGER.info("RS485 IPC subscriber disabled")
            return
        if zmq is None:
            raise RuntimeError("rs485_ipc.enabled=true requires pyzmq. Install with: uv add pyzmq")
        self._context = zmq.Context.instance()
        self._socket = self._context.socket(zmq.SUB)
        self._socket.setsockopt(zmq.RCVHWM, int(self.cfg.rs485_ipc.receive_hwm))
        self._socket.setsockopt(zmq.LINGER, 0)
        topic = str(self.cfg.rs485_ipc.topic).encode("utf-8")
        self._socket.setsockopt(zmq.SUBSCRIBE, topic)
        self._socket.connect(str(self.cfg.rs485_ipc.connect))
        self._thread = threading.Thread(target=self._run, name="rs485-ipc-subscriber", daemon=True)
        self._thread.start()
        LOGGER.info("RS485 IPC subscriber connected to %s topic=%s", self.cfg.rs485_ipc.connect, self.cfg.rs485_ipc.topic)

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
        while not self._stop_event.is_set():
            try:
                parts = self._socket.recv_multipart(flags=zmq.NOBLOCK)
            except zmq.Again:
                time.sleep(0.002)
                continue
            except Exception as exc:
                LOGGER.warning("RS485 IPC receive warning: %s", exc)
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

            with self._lock:
                if sample.seq is not None:
                    if self._last_seq is not None and sample.seq != self._last_seq + 1:
                        self._gap_count += 1
                        if self._gap_count == 1 or self._gap_count % 20 == 0:
                            LOGGER.warning("RS485 IPC sequence gap #%d: last=%s current=%s", self._gap_count, self._last_seq, sample.seq)
                    self._last_seq = sample.seq
                self._buffer.append(sample)
                self._last_valid = sample
                self._received_count += 1

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
        )

    def select(self, target_lsl_ts: float) -> RS485Selection:
        if not self.enabled:
            return RS485Selection(sample=None, age_s=math.nan, missing_reason="disabled")

        max_age_s = max(0.0, float(self.cfg.rs485_ipc.max_age_s))
        max_future_s = max(0.0, float(self.cfg.rs485_ipc.max_future_s))
        missing_policy = str(self.cfg.rs485_ipc.missing_policy)
        stale_policy = str(self.cfg.rs485_ipc.stale_policy)
        now_monotonic = time.monotonic()

        with self._lock:
            buffer_snapshot = list(self._buffer)
            last_valid = self._last_valid
            received_count = self._received_count
            malformed_count = self._malformed_count
            gap_count = self._gap_count

        # Select the closest RS485 sample in the allowed fusion window.
        # Active-Send arrives in small bursts; closest-sample fusion is better
        # synchronized than simply holding the newest causal sample.
        chosen: Optional[RS485IpcSample] = None
        best_abs_age = math.inf
        lower_bound = target_lsl_ts - max_age_s
        upper_bound = target_lsl_ts + max_future_s
        for candidate in reversed(buffer_snapshot):
            candidate_ts = candidate.host_lsl_ts
            if candidate_ts > upper_bound:
                continue
            if candidate_ts < lower_bound:
                # Buffer is append-ordered by timestamp in normal operation; once
                # we are older than the lower bound while scanning backwards, the
                # remaining candidates will be older too.
                break
            abs_age = abs(target_lsl_ts - candidate_ts)
            if abs_age < best_abs_age:
                chosen = candidate
                best_abs_age = abs_age

        if chosen is None:
            if missing_policy == "hold_last" and last_valid is not None:
                age = target_lsl_ts - last_valid.host_lsl_ts
                return RS485Selection(sample=last_valid, age_s=age, missing_reason="hold_last_missing")
            self._log_status_if_due(received_count, malformed_count, gap_count, reason="no_frames")
            return RS485Selection(sample=None, age_s=math.nan, missing_reason="missing")

        age_s = target_lsl_ts - chosen.host_lsl_ts
        if abs(age_s) > max_age_s:
            if stale_policy == "hold_last":
                return RS485Selection(sample=chosen, age_s=age_s, missing_reason="hold_last_stale")
            self._log_status_if_due(
                received_count,
                malformed_count,
                gap_count,
                reason=f"stale age={age_s:.6f}s window=[-{max_age_s:.3f},+{max_future_s:.3f}]",
            )
            return RS485Selection(sample=None, age_s=age_s, missing_reason="stale")

        if now_monotonic - self._last_status_log_monotonic >= float(self.cfg.rs485_ipc.log_status_every_s):
            self._last_status_log_monotonic = now_monotonic
            LOGGER.info(
                "RS485 IPC status: received=%d malformed=%d gaps=%d latest_mode=%s latest_age_s=%.6f",
                received_count,
                malformed_count,
                gap_count,
                chosen.mode,
                age_s,
            )
        return RS485Selection(sample=chosen, age_s=age_s, missing_reason="")

    def _log_status_if_due(self, received_count: int, malformed_count: int, gap_count: int, reason: str) -> None:
        now = time.monotonic()
        if now - self._last_status_log_monotonic < float(self.cfg.rs485_ipc.log_status_every_s):
            return
        self._last_status_log_monotonic = now
        LOGGER.warning(
            "RS485 IPC unavailable/stale (%s); publishing NaN. received=%d malformed=%d gaps=%d",
            reason,
            received_count,
            malformed_count,
            gap_count,
        )


def configure_logging(level_name: str) -> None:
    level = getattr(logging, str(level_name).upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
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


def build_source_id(cfg: DictConfig, port_meta: dict[str, Any]) -> str:
    explicit = cfg.stream.get("source_id")
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


def build_outlet(cfg: DictConfig, source_id: str) -> StreamOutlet:
    info = StreamInfo(
        str(cfg.stream.name),
        str(cfg.stream.type),
        5,
        IRREGULAR_RATE,
        cf_double64,
        source_id,
    )

    desc = info.desc()
    desc.append_child_value("manufacturer", str(cfg.stream.manufacturer))
    desc.append_child_value("device_name", str(cfg.stream.device_name))
    desc.append_child_value("protocol", "arduino_serial_plus_rs485_ipc_to_lsl")
    desc.append_child_value("sampling_model", "irregular_fused")
    desc.append_child_value("rs485_ipc_enabled", str(bool(cfg.rs485_ipc.enabled)))
    desc.append_child_value("rs485_ipc_endpoint", str(cfg.rs485_ipc.connect))

    channels = desc.append_child("channels")

    channel_specs = [
        (cfg.stream.clock_channel_label, cfg.stream.clock_channel_type, cfg.stream.clock_unit),
        (cfg.stream.raw_channel_label, cfg.stream.raw_channel_type, cfg.stream.value_unit),
        (cfg.stream.filtered_channel_label, cfg.stream.filtered_channel_type, cfg.stream.value_unit),
        (cfg.stream.rs485_raw_channel_label, cfg.stream.rs485_raw_channel_type, cfg.stream.rs485_value_unit),
        (cfg.stream.rs485_clock_channel_label, cfg.stream.rs485_clock_channel_type, cfg.stream.rs485_clock_unit),
    ]
    for label, channel_type, unit in channel_specs:
        channel = channels.append_child("channel")
        channel.append_child_value("label", str(label))
        channel.append_child_value("type", str(channel_type))
        channel.append_child_value("unit", str(unit))

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


@hydra.main(version_base=None, config_path="conf", config_name="config")
def app(cfg: DictConfig) -> None:
    configure_logging(str(cfg.logging.level))
    LOGGER.info("Starting bridge with config:\n%s", OmegaConf.to_yaml(cfg))

    csv_path = Path(to_absolute_path(str(cfg.csv.path)))
    sink = CsvSink(
        path=csv_path,
        append=bool(cfg.csv.append),
        flush_every_n_rows=int(cfg.csv.flush_every_n_rows),
    )
    parser = LineParser(cfg)

    rs485_subscriber = RS485IpcSubscriber(cfg)
    rs485_subscriber.start()

    sample_count = 0
    try:
        while True:
            try:
                LOGGER.info("Opening serial port %s @ %s baud", cfg.serial.port, cfg.serial.baudrate)
                with Serial(
                    port=str(cfg.serial.port),
                    baudrate=int(cfg.serial.baudrate),
                    timeout=float(cfg.serial.timeout_s),
                ) as ser:
                    settle_serial_input(ser, float(cfg.serial.startup_settle_s))
                    port_meta = find_port_metadata(str(cfg.serial.port))
                    source_id = build_source_id(cfg, port_meta)
                    outlet = build_outlet(cfg, source_id)
                    processor = build_processor(cfg)
                    time_resolver = SampleTimeResolver(cfg)
                    LOGGER.info(
                        "LSL outlet ready: name=%s type=%s source_id=%s csv=%s",
                        cfg.stream.name,
                        cfg.stream.type,
                        source_id,
                        csv_path,
                    )

                    while True:
                        raw_line = ser.readline(int(cfg.serial.max_line_bytes) + 1)
                        if not raw_line:
                            continue
                        if len(raw_line) > int(cfg.serial.max_line_bytes) and not raw_line.endswith(b"\n"):
                            LOGGER.warning("Dropped overlong serial line; flushing input buffer")
                            ser.reset_input_buffer()
                            continue

                        arrival_unix_time_ns = time.time_ns()
                        arrival_lsl_time = local_clock() - float(cfg.serial.transport_latency_s)
                        sample = parser.feed(raw_line, arrival_lsl_time, arrival_unix_time_ns)
                        if sample is None:
                            continue

                        sample_time_s = time_resolver.resolve(sample)
                        filtered_value = float(processor.process(sample.value, sample_time_s))

                        rs485_selection = rs485_subscriber.select(sample.lsl_timestamp)
                        rs485_sample = rs485_selection.sample
                        rs485_raw = math.nan if rs485_sample is None else rs485_sample.rs485_raw
                        rs485_clock = math.nan if rs485_sample is None else rs485_sample.rs485_clock

                        outlet.push_sample(
                            [
                                float(sample.device_clock_us),
                                float(sample.value),
                                filtered_value,
                                float(rs485_raw),
                                float(rs485_clock),
                            ],
                            timestamp=sample.lsl_timestamp,
                            pushthrough=True,
                        )
                        sink.write(sample, filtered_value, rs485_selection)
                        sample_count += 1

                        if sample_count == 1 or sample_count % int(cfg.logging.log_every_n_samples) == 0:
                            LOGGER.info(
                                "Published samples=%d latest_clock_us=%d raw=%s filtered=%s rs485_raw=%s rs485_clock=%s rs485_missing=%s parser=%s",
                                sample_count,
                                sample.device_clock_us,
                                sample.value,
                                filtered_value,
                                rs485_raw,
                                rs485_clock,
                                rs485_selection.missing_reason or "ok",
                                sample.parser_mode,
                            )

            except SerialException as exc:
                LOGGER.exception("Serial port failure: %s", exc)
                LOGGER.info("Retrying in %.2f s", float(cfg.serial.reconnect_backoff_s))
                time.sleep(float(cfg.serial.reconnect_backoff_s))

    except KeyboardInterrupt:
        LOGGER.info("Stopping on user request")
    finally:
        rs485_subscriber.stop()
        sink.close()


def main() -> int:
    try:
        app()
        return 0
    except Exception:
        LOGGER.exception("Fatal error in bridge")
        return 1


if __name__ == "__main__":
    sys.exit(main())
