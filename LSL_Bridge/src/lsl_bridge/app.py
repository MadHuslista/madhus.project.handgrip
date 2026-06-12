# @package lsl_bridge.app
#  @brief LSL Bridge application orchestration entry point.
##
"""
LSL Bridge application entry point.

Contains the Hydra-decorated ``app()`` function that orchestrates the full
bridge lifecycle:

1. Configure hierarchical logging (console + file).
2. Build the component event outlet.
3. Open CSV sinks and LSL outlets.
4. Start the RS485 IPC reference publisher (background thread).
5. Run the target serial read loop (foreground, auto-reconnects on error).
6. On ``KeyboardInterrupt``: emit ``bridge_stop``, flush and close all sinks.

Run via::

    python -m lsl_bridge
    lsl-bridge

Override any config key at the command line::

    python -m lsl_bridge serial.port=/dev/ttyUSB0
    python -m lsl_bridge logging=debug
    python -m lsl_bridge logging.level=DEBUG
"""

from __future__ import annotations

import logging
import sys
import time
from datetime import datetime
from pathlib import Path

import hydra
from hydra.utils import to_absolute_path
from omegaconf import DictConfig, OmegaConf
from pylsl import local_clock
from serial import Serial, SerialException

import __main__
from lsl_bridge.core.parser import D2LineParser
from lsl_bridge.core.processing import build_processor
from lsl_bridge.core.timestamping import SampleTimeResolver, TargetTimestampResolver
from lsl_bridge.io.csv_sinks import ReferenceCsvSink, TargetCsvSink, apply_timestamp_suffix
from lsl_bridge.io.lsl_outlets import (
    build_reference_outlet,
    build_target_outlet,
    build_target_source_id,
)
from lsl_bridge.io.serial_utils import find_port_metadata, settle_serial_input
from lsl_bridge.logging_setup import configure_logging
from lsl_bridge.publishers.events import ComponentEventOutlet
from lsl_bridge.publishers.reference import RS485IpcReferencePublisher

_log = logging.getLogger(__name__)

LIBRARY_ROOT = Path(__file__).parent.parent.parent.absolute()

# ---------------------------------------------------------------------------
# Sink factory helpers
# ---------------------------------------------------------------------------


def _open_target_sink(cfg: DictConfig, run_timestamp: str) -> TargetCsvSink | None:
    if not bool(cfg.csv.target.enabled):
        return None
    write_mode = str(cfg.csv.target.write_mode)
    path = Path(to_absolute_path(str(cfg.csv.target.path)))
    if write_mode == "timestamped":
        path = apply_timestamp_suffix(path, run_timestamp)
    return TargetCsvSink(
        path,
        write_mode,
        int(cfg.csv.target.flush_every_n_rows),
    )


def _open_reference_sink(cfg: DictConfig, run_timestamp: str) -> ReferenceCsvSink | None:
    if not bool(cfg.csv.reference.enabled):
        return None
    write_mode = str(cfg.csv.reference.write_mode)
    path = Path(to_absolute_path(str(cfg.csv.reference.path)))
    if write_mode == "timestamped":
        path = apply_timestamp_suffix(path, run_timestamp)
    return ReferenceCsvSink(
        path,
        write_mode,
        int(cfg.csv.reference.flush_every_n_rows),
    )


# ---------------------------------------------------------------------------
# Hydra application
# ---------------------------------------------------------------------------


@hydra.main(version_base=None, config_path=f"{LIBRARY_ROOT}/conf", config_name="config")
# @brief Run the Hydra-driven LSL bridge lifecycle.
#  @param cfg Fully merged Hydra configuration.
#  @return None.
def app(cfg: DictConfig) -> None:
    """
    Main bridge application, driven by Hydra config.

    Args:
        cfg: Fully-merged Hydra ``DictConfig`` object.

    """
    configure_logging(cfg)
    _log.info(
        "Starting calibration-schema LSL bridge (v%s) with config:\n%s",
        _bridge_version(),
        OmegaConf.to_yaml(cfg),
    )

    events = ComponentEventOutlet(cfg)
    events.emit(
        "bridge_start",
        config_schema=str(cfg.schema.version),
        session_id=cfg.session.get("session_id"),
    )

    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target_sink = _open_target_sink(cfg, run_timestamp)
    reference_sink = _open_reference_sink(cfg, run_timestamp)
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
                _log.info(
                    "Opening target serial port %s @ %s baud",
                    cfg.serial.port,
                    cfg.serial.baudrate,
                )
                with Serial(
                    port=str(cfg.serial.port),
                    baudrate=int(cfg.serial.baudrate),
                    timeout=float(cfg.serial.timeout_s),
                ) as ser:
                    settle_serial_input(ser, float(cfg.serial.startup_settle_s))
                    port_meta = find_port_metadata(str(cfg.serial.port))
                    source_id = build_target_source_id(cfg, port_meta)
                    target_outlet = build_target_outlet(cfg, source_id)
                    events.emit(
                        "target_serial_connected",
                        port=str(cfg.serial.port),
                        baudrate=int(cfg.serial.baudrate),
                        source_id=source_id,
                        port_metadata=port_meta,
                    )
                    _log.info(
                        "Target LSL outlet ready: name=%s source_id=%s",
                        cfg.streams.target.name,
                        source_id,
                    )

                    while True:
                        raw_line = ser.readline(int(cfg.serial.max_line_bytes) + 1)
                        if not raw_line:
                            continue

                        if len(raw_line) > int(cfg.serial.max_line_bytes) and not raw_line.endswith(b"\n"):
                            events.emit("target_overlong_line")
                            _log.warning("Dropped overlong target serial line; flushing input buffer")
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
                            _log.info(
                                "Target LSL status: published=%d seq=%d clock_us=%d "
                                "raw_count=%s current_units=%s status=%d timestamp=%.6f",
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
                _log.exception("Target serial port failure: %s", exc)
                time.sleep(float(cfg.serial.reconnect_backoff_s))

    except KeyboardInterrupt:
        _log.info("Stopping on user request (KeyboardInterrupt).")
        events.emit("bridge_stop", reason="keyboard_interrupt")

    finally:
        reference_publisher.stop()
        if target_sink is not None:
            target_sink.close()
        if reference_sink is not None:
            reference_sink.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


# @brief Return the installed LSL Bridge package version.
#  @return Semantic version string, or "unknown" if unavailable.
def _bridge_version() -> str:
    try:
        from lsl_bridge import __version__

        return __version__
    except Exception:
        return "unknown"


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


# @brief CLI entry point for module and console-script execution.
#  @return Process exit status code.
def main() -> int:
    """Wrapper called by the ``lsl-bridge`` console script and ``__main__.py``."""
    try:
        app()
        return 0
    except Exception:
        _log.exception("Fatal error in bridge")
        return 1


if __name__ == "__main__":
    sys.exit(main())
