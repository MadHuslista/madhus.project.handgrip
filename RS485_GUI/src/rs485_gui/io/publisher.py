"""ZeroMQ PUB socket publisher for decoded RS485 MeasurementFrame data.

Publishes on two topics:
  ``ipc.topic``       — high-rate MeasurementFrame records (consumed by LSL Bridge)
  ``ipc.event_topic`` — operational events (session connect/disconnect, etc.)

The publisher is created lazily and bound only when the user starts an
acquisition session.  NiceGUI may re-execute the script during page serving;
binding ZMQ at application construction time would produce a false port-conflict
error on the second execution.

Dependency chain: models, core/signals  (no UI)
"""
from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime
from typing import Any

from omegaconf import DictConfig

from rs485_gui.core.codec import lsl_local_clock
from rs485_gui.core.signals import extract_signal_value
from rs485_gui.models import MeasurementFrame

LOGGER = logging.getLogger(__name__)

try:
    import zmq  # type: ignore[import]
except Exception:  # pragma: no cover — optional dependency
    zmq = None  # type: ignore[assignment]


class MeasurementFramePublisher:
    """Best-effort ZeroMQ PUB-socket publisher for decoded RS485 frames."""

    SCHEMA = 'rs485.measurement.v1'

    def __init__(self, cfg: DictConfig) -> None:
        self.cfg = cfg
        self.enabled = bool(cfg.ipc.enabled)
        self.transport = str(cfg.ipc.transport)
        self.bind = str(cfg.ipc.bind)
        self.topic = str(cfg.ipc.topic)
        self.event_topic = str(cfg.ipc.event_topic)
        self.signal_key = str(cfg.ipc.signal_key)
        self.drop_on_backpressure = bool(cfg.ipc.drop_on_backpressure)

        # Set lazily from AppState at first use
        self.session_id: str = ''
        self.board_profile: dict[str, Any] = {}

        self._context: Any = None
        self._socket: Any = None
        self._seq: int = 0
        self._dropped_publish_errors: int = 0
        self._published: int = 0
        self._last_log_monotonic: float = 0.0
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Bind the ZMQ PUB socket.  Idempotent if already started."""
        if not self.enabled:
            LOGGER.info('RS485 IPC publisher disabled (ipc.enabled=false)')
            return
        if self._socket is not None:
            return
        if self.transport != 'zmq_pub':
            raise ValueError(
                f'Unsupported ipc.transport={self.transport!r}; only zmq_pub is implemented'
            )
        if zmq is None:
            raise RuntimeError(
                'ipc.enabled=true requires pyzmq. Install with: uv add pyzmq'
            )
        try:
            from pylsl import local_clock  # type: ignore[import] # noqa: F401
        except Exception:
            if bool(self.cfg.ipc.require_pylsl_clock):
                raise RuntimeError(
                    'ipc.enabled=true requires pylsl for LSL-local RS485 timestamps. '
                    'Install with: uv add pylsl'
                )

        self._context = zmq.Context.instance()
        socket = self._context.socket(zmq.PUB)
        socket.setsockopt(zmq.SNDHWM, int(self.cfg.ipc.send_hwm))
        socket.setsockopt(zmq.LINGER, int(self.cfg.ipc.linger_ms))
        try:
            socket.bind(self.bind)
        except Exception as exc:
            try:
                socket.close(0)
            except Exception:
                pass
            raise RuntimeError(
                f'Could not bind RS485 IPC publisher to {self.bind}. '
                'Another rs485-gui process is probably already bound to that endpoint, '
                'or a previous process did not exit cleanly. '
                'Stop the other process or change ipc.bind.'
            ) from exc
        self._socket = socket
        LOGGER.info(
            'RS485 IPC publisher bound to %s topic=%s event_topic=%s signal_key=%s',
            self.bind, self.topic, self.event_topic, self.signal_key,
        )

    def stop(self) -> None:
        """Close the ZMQ socket.  Idempotent if already stopped."""
        with self._lock:
            if self._socket is not None:
                try:
                    self._socket.close(0)
                except Exception:
                    pass
            self._socket = None

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------

    def publish_frames(self, frames: list[MeasurementFrame]) -> None:
        """Publish *frames* on the measurement topic."""
        if not self.enabled or not frames:
            return
        with self._lock:
            if self._socket is None:
                return
            flags = zmq.NOBLOCK if self.drop_on_backpressure else 0
            for frame in frames:
                record = self._build_record(frame)
                if record is None:
                    continue
                try:
                    self._socket.send_multipart(
                        [
                            self.topic.encode('utf-8'),
                            json.dumps(record, ensure_ascii=False, separators=(',', ':')).encode('utf-8'),
                        ],
                        flags=flags,
                    )
                    self._published += 1
                except Exception as exc:
                    self._dropped_publish_errors += 1
                    if self._dropped_publish_errors == 1 or self._dropped_publish_errors % 100 == 0:
                        LOGGER.warning(
                            'RS485 IPC publish drop #%d: %s',
                            self._dropped_publish_errors, exc,
                        )
        self._log_status_if_due()

    def publish_event(self, event: str, **payload: Any) -> None:
        """Publish a structured operational event on the event topic.

        Events are diagnostic and must never perturb acquisition; all exceptions
        are silently swallowed.
        """
        if not self.enabled:
            return
        with self._lock:
            if self._socket is None:
                return
            record = {
                'schema': 'rs485.event.v1',
                'session_id': self.session_id,
                'event': event,
                'host_unix_ts': time.time(),
                'host_ts_iso': datetime.now().isoformat(timespec='milliseconds'),
                'board_profile': self.board_profile,
                **payload,
            }
            try:
                self._socket.send_multipart(
                    [
                        self.event_topic.encode('utf-8'),
                        json.dumps(record, ensure_ascii=False, separators=(',', ':')).encode('utf-8'),
                    ],
                    flags=zmq.NOBLOCK if self.drop_on_backpressure else 0,
                )
            except Exception:
                pass  # events are diagnostic; never perturb acquisition

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_record(self, frame: MeasurementFrame) -> dict[str, Any] | None:
        value = extract_signal_value(frame, self.signal_key)
        if value is None:
            self._dropped_publish_errors += 1
            if self._dropped_publish_errors == 1 or self._dropped_publish_errors % 100 == 0:
                LOGGER.warning(
                    'RS485 IPC skipped frame without numeric signal_key=%s', self.signal_key
                )
            return None

        interpreted = frame.interpreted
        host_lsl_ts = interpreted.get('host_lsl_ts') or lsl_local_clock()
        rs485_clock = interpreted.get('rs485_clock', host_lsl_ts)
        clock_source = str(
            interpreted.get('rs485_clock_source', interpreted.get('timestamp_source', 'unknown'))
        )
        self._seq += 1
        status_word = interpreted.get('status_word')
        return {
            'schema': self.SCHEMA,
            'seq': self._seq,
            'session_id': frame.session_id or self.session_id,
            'mode': frame.mode,
            'signal_key': self.signal_key,
            # Canonical v2 fields consumed by the LSL Bridge
            'reference_force_N': float(value),
            'reference_clock_s': float(rs485_clock),
            'reference_status': 0 if status_word is None else int(status_word),
            # Retained aliases for human grep/debug
            'rs485_raw': float(value),
            'rs485_clock': float(rs485_clock),
            'rs485_clock_source': clock_source,
            'host_lsl_ts': float(host_lsl_ts),
            'host_unix_ts': float(frame.host_ts),
            'host_ts_iso': frame.host_ts_iso,
            'unit_label': interpreted.get('unit_label'),
            'status_word': status_word,
            'timestamp_source': interpreted.get('timestamp_source'),
            'configured_frequency_hz': interpreted.get('configured_frequency_hz'),
            'parsed_from': interpreted.get('parsed_from'),
            'board_profile': frame.board_profile or self.board_profile,
        }

    def _log_status_if_due(self) -> None:
        interval_s = float(self.cfg.ipc.log_every_s)
        if interval_s <= 0:
            return
        now = time.monotonic()
        if now - self._last_log_monotonic < interval_s:
            return
        self._last_log_monotonic = now
        LOGGER.info(
            'RS485 IPC publisher status: published=%d publish_drops=%d topic=%s',
            self._published, self._dropped_publish_errors, self.topic,
        )
