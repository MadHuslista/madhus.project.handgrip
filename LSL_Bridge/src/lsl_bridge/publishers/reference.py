"""RS485 IPC reference stream publisher for the LSL Bridge.

``RS485IpcReferencePublisher`` subscribes to the RS485_GUI ZMQ PUB socket,
decodes ``rs485.measurement.v1`` JSON messages, and republishes the data as
a regular LSL stream (HandgripReference).

The publisher runs in a background daemon thread so that the main thread can
continue reading the Arduino serial port without blocking.

Key design decisions:
* ZMQ ``NOBLOCK`` receive with a short ``poll_interval_s`` sleep keeps CPU
  usage low while maintaining sub-millisecond latency under normal load.
* Only ``zmq.ZMQError`` is caught in the receive loop; other exceptions
  propagate and crash the thread loudly rather than being silently swallowed.
* The ``expected_schema`` config key is enforced on every message so that
  protocol mismatches are detected immediately.
* Legacy field aliases (``rs485_raw``, ``rs485_clock``, ``status_word``) have
  been **removed**.  Only canonical ``rs485.measurement.v1`` field names are
  accepted.
"""

from __future__ import annotations

import json
import logging
import math
import threading
import time
from typing import Any

from omegaconf import DictConfig
from pylsl import StreamOutlet, local_clock

from lsl_bridge.io.csv_sinks import ReferenceCsvSink
from lsl_bridge.publishers.events import ComponentEventOutlet
from lsl_bridge.types import ReferenceSample

try:
    import zmq
except ImportError:  # optional runtime dependency
    zmq = None  # type: ignore[assignment]

_log = logging.getLogger(__name__)


class RS485IpcReferencePublisher:
    """Subscribes to RS485_GUI IPC and republishes canonical reference LSL.

    Args:
        cfg:    Full Hydra ``DictConfig``.
        outlet: Pre-built ``StreamOutlet`` for the reference stream, or
                ``None`` if the reference stream is disabled.
        sink:   Optional ``ReferenceCsvSink`` for local persistence.
        events: ``ComponentEventOutlet`` for structured operational events.
    """

    def __init__(
        self,
        cfg: DictConfig,
        outlet: StreamOutlet | None,
        sink: ReferenceCsvSink | None,
        events: ComponentEventOutlet,
    ) -> None:
        self._cfg = cfg
        self.enabled = bool(cfg.rs485_ipc.enabled) and bool(cfg.streams.reference.enabled)
        self._outlet = outlet
        self._sink = sink
        self._events = events
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._context: Any = None
        self._socket: Any = None
        self._last_status_log_monotonic: float = 0.0
        self._published_count: int = 0
        self._malformed_count: int = 0
        self._gap_count: int = 0
        self._last_seq: int | None = None

    # ------------------------------------------------------------------
    # Public lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Connect the ZMQ socket and start the background publisher thread.

        Raises:
            RuntimeError: If the reference stream is enabled but no outlet was
                          provided, or if ``pyzmq`` is not installed.
        """
        if not self.enabled:
            _log.info("Reference RS485 IPC publisher disabled.")
            return

        if self._outlet is None:
            raise RuntimeError(
                "Reference stream is enabled but no StreamOutlet was provided."
            )
        if zmq is None:
            raise RuntimeError(
                "rs485_ipc.enabled=true requires pyzmq. "
                "Install it with: pip install pyzmq"
            )

        self._context = zmq.Context.instance()
        self._socket = self._context.socket(zmq.SUB)
        self._socket.setsockopt(zmq.RCVHWM, int(self._cfg.rs485_ipc.receive_hwm))
        self._socket.setsockopt(zmq.LINGER, 0)
        topic = str(self._cfg.rs485_ipc.topic).encode("utf-8")
        self._socket.setsockopt(zmq.SUBSCRIBE, topic)
        self._socket.connect(str(self._cfg.rs485_ipc.connect))

        self._thread = threading.Thread(
            target=self._run,
            name="rs485-reference-lsl-publisher",
            daemon=True,
        )
        self._thread.start()

        self._events.emit(
            "reference_ipc_connected",
            endpoint=str(self._cfg.rs485_ipc.connect),
            topic=str(self._cfg.rs485_ipc.topic),
        )
        _log.info(
            "Reference IPC publisher connected: endpoint=%s topic=%s",
            self._cfg.rs485_ipc.connect,
            self._cfg.rs485_ipc.topic,
        )

    def stop(self) -> None:
        """Signal the background thread to stop and wait for it to exit."""
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        if self._socket is not None:
            try:
                self._socket.close(0)
            except Exception:
                pass
        self._socket = None
        _log.info("Reference IPC publisher stopped.")

    # ------------------------------------------------------------------
    # Background thread
    # ------------------------------------------------------------------

    def _run(self) -> None:
        assert self._socket is not None
        assert self._outlet is not None

        poll_interval = float(self._cfg.rs485_ipc.poll_interval_s)
        error_backoff = float(self._cfg.rs485_ipc.error_backoff_s)
        log_malformed_every_n = int(self._cfg.rs485_ipc.log_malformed_every_n)

        while not self._stop_event.is_set():
            try:
                parts = self._socket.recv_multipart(flags=zmq.NOBLOCK)
            except zmq.Again:
                time.sleep(poll_interval)
                continue
            except zmq.ZMQError as exc:
                # Narrow catch: only transport-level errors; programmer errors propagate.
                _log.warning("Reference IPC transport error: %s", exc)
                time.sleep(error_backoff)
                continue

            try:
                record = json.loads(parts[-1].decode("utf-8"))
                sample = self._decode_record(record)
            except Exception as exc:
                self._malformed_count += 1
                if (
                    self._malformed_count == 1
                    or self._malformed_count % log_malformed_every_n == 0
                ):
                    self._events.emit(
                        "reference_ipc_malformed",
                        count=self._malformed_count,
                        error=str(exc),
                    )
                    _log.warning(
                        "Dropped malformed RS485 IPC message #%d: %s",
                        self._malformed_count,
                        exc,
                    )
                continue

            if sample.sequence >= 0:
                if self._last_seq is not None and sample.sequence != self._last_seq + 1:
                    self._gap_count += 1
                    self._events.emit(
                        "reference_sequence_gap",
                        last_seq=self._last_seq,
                        current_seq=sample.sequence,
                        count=self._gap_count,
                    )
                    _log.warning(
                        "Reference RS485 sequence gap #%d: last=%s current=%s",
                        self._gap_count,
                        self._last_seq,
                        sample.sequence,
                    )
                self._last_seq = sample.sequence

            timestamp = (
                sample.host_lsl_ts
                if math.isfinite(sample.host_lsl_ts)
                else sample.received_lsl_ts
            )
            self._outlet.push_sample(
                [
                    float(sample.sequence),
                    float(sample.reference_clock_s),
                    float(sample.reference_force_N),
                    float(sample.status),
                ],
                timestamp=timestamp,
                pushthrough=True,
            )
            if self._sink is not None:
                self._sink.write(sample, timestamp)
            self._published_count += 1
            self._log_status_if_due(sample, timestamp)

    # ------------------------------------------------------------------
    # IPC message decoding
    # ------------------------------------------------------------------

    def _decode_record(self, record: dict[str, Any]) -> ReferenceSample:
        """Decode one RS485 IPC JSON record into a ``ReferenceSample``.

        Only the canonical ``rs485.measurement.v1`` field names are accepted.
        Legacy aliases (``rs485_raw``, ``rs485_clock``, ``status_word``) have
        been removed.  If the schema field does not match
        ``cfg.rs485_ipc.expected_schema``, a ``ValueError`` is raised and the
        message is counted as malformed.

        Args:
            record: Parsed JSON dict from the ZMQ message.

        Returns:
            A fully-populated ``ReferenceSample``.

        Raises:
            ValueError: For schema mismatch or missing required fields.
        """
        expected = str(self._cfg.rs485_ipc.expected_schema)
        actual_schema = str(record.get("schema", ""))
        if actual_schema != expected:
            raise ValueError(
                f"Unsupported IPC schema: expected={expected!r} received={actual_schema!r}"
            )

        force = record.get("reference_force_N")
        clock = record.get("reference_clock_s")
        host_lsl_ts = record.get("host_lsl_ts")

        if force is None or clock is None or host_lsl_ts is None:
            raise ValueError(
                "Missing required fields: reference_force_N, reference_clock_s, host_lsl_ts"
            )

        status_raw = record.get("reference_status", 0)
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
            clock_source=str(record.get("clock_source", "unknown")),
            unit_label=str(record.get("unit_label", "N")),
            status=status,
            timestamp_source=str(record.get("timestamp_source", "host_lsl_ts")),
            configured_frequency_hz=(
                float(configured_frequency_hz)
                if configured_frequency_hz is not None
                else math.nan
            ),
            session_id=record.get("session_id"),
            board_profile=record.get("board_profile", {}) or {},
        )

    # ------------------------------------------------------------------
    # Status logging
    # ------------------------------------------------------------------

    def _log_status_if_due(self, sample: ReferenceSample, timestamp: float) -> None:
        now = time.monotonic()
        log_interval = float(self._cfg.rs485_ipc.log_status_every_s)
        if self._published_count == 1 or now - self._last_status_log_monotonic >= log_interval:
            self._last_status_log_monotonic = now
            _log.info(
                "Reference LSL status: published=%d malformed=%d gaps=%d "
                "latest_seq=%s force_N=%s timestamp_age_s=%.6f mode=%s",
                self._published_count,
                self._malformed_count,
                self._gap_count,
                sample.sequence,
                sample.reference_force_N,
                local_clock() - timestamp,
                sample.mode,
            )
