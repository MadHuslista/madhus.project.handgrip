from __future__ import annotations

import binascii
import csv
import importlib
import logging
import re
import sys
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


class CsvSink:
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
        3,
        IRREGULAR_RATE,
        cf_double64,
        source_id,
    )

    desc = info.desc()
    desc.append_child_value("manufacturer", str(cfg.stream.manufacturer))
    desc.append_child_value("device_name", str(cfg.stream.device_name))
    desc.append_child_value("protocol", "serial_to_lsl_bridge")
    desc.append_child_value("sampling_model", "irregular")

    channels = desc.append_child("channels")

    channel_specs = [
        (cfg.stream.clock_channel_label, cfg.stream.clock_channel_type, cfg.stream.clock_unit),
        (cfg.stream.raw_channel_label, cfg.stream.raw_channel_type, cfg.stream.value_unit),
        (cfg.stream.filtered_channel_label, cfg.stream.filtered_channel_type, cfg.stream.value_unit),
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

                        outlet.push_sample(
                            [float(sample.device_clock_us), float(sample.value), filtered_value],
                            timestamp=sample.lsl_timestamp,
                            pushthrough=True,
                        )
                        sink.write(sample, filtered_value)
                        sample_count += 1

                        if sample_count == 1 or sample_count % int(cfg.logging.log_every_n_samples) == 0:
                            LOGGER.info(
                                "Published samples=%d latest_clock_us=%d raw=%s filtered=%s parser=%s",
                                sample_count,
                                sample.device_clock_us,
                                sample.value,
                                filtered_value,
                                sample.parser_mode,
                            )

            except SerialException as exc:
                LOGGER.exception("Serial port failure: %s", exc)
                LOGGER.info("Retrying in %.2f s", float(cfg.serial.reconnect_backoff_s))
                time.sleep(float(cfg.serial.reconnect_backoff_s))

    except KeyboardInterrupt:
        LOGGER.info("Stopping on user request")
    finally:
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
