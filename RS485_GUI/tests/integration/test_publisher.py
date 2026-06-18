"""Integration tests for rs485_gui.io.publisher.MeasurementFramePublisher.

Uses a fake ZMQ module so no real socket is bound; the focus is the async
publisher-thread mechanics (enqueue, drain-on-stop, sync fallback).
"""

from __future__ import annotations

import threading
import time

import pytest
from omegaconf import OmegaConf

import rs485_gui.io.publisher as publisher_mod
from rs485_gui.io.publisher import MeasurementFramePublisher
from rs485_gui.models import MeasurementFrame


class _FakeSocket:
    def __init__(self) -> None:
        self.sent: list[list[bytes]] = []
        self.closed = False
        self._lock = threading.Lock()

    def setsockopt(self, *_a) -> None:
        pass

    def bind(self, _addr) -> None:
        pass

    def send_multipart(self, parts, flags=0) -> None:
        with self._lock:
            self.sent.append(parts)

    def close(self, _linger=0) -> None:
        self.closed = True


class _FakeContext:
    def __init__(self) -> None:
        self.sock = _FakeSocket()

    def socket(self, _kind):
        return self.sock


class _FakeZmq:
    PUB = 1
    NOBLOCK = 2
    SNDHWM = 3
    LINGER = 4

    def __init__(self) -> None:
        self._ctx = _FakeContext()

    class _CtxFactory:
        def __init__(self, ctx):
            self._ctx = ctx

        def instance(self):
            return self._ctx

    @property
    def Context(self):  # noqa: N802 — mirrors zmq.Context.instance()
        return _FakeZmq._CtxFactory(self._ctx)


@pytest.fixture
def fake_zmq(monkeypatch):
    fz = _FakeZmq()
    monkeypatch.setattr(publisher_mod, "zmq", fz)
    return fz


def _make_cfg(async_publish=True):
    return OmegaConf.create(
        {
            "ipc": {
                "enabled": True,
                "transport": "zmq_pub",
                "bind": "tcp://127.0.0.1:5599",
                "topic": "rs485.measurement.v1",
                "event_topic": "rs485.event.v1",
                "signal_key": "net_value",
                "send_hwm": 2000,
                "linger_ms": 0,
                "drop_on_backpressure": True,
                "async_publish": async_publish,
                "publish_queue_maxsize": 200000,
                "require_pylsl_clock": False,
                "log_every_s": 0.0,
            }
        }
    )


def _frame(i: float) -> MeasurementFrame:
    return MeasurementFrame(
        host_ts=1000.0 + i * 0.002,
        host_ts_iso="2026-06-18T05:00:00.000",
        mode="active_send",
        raw_transport={"response_hex": "01 03 16"},
        interpreted={
            "net_value": float(i),
            "reference_force_N": float(i),
            "rs485_clock": 1000.0 + i * 0.002,
            "host_lsl_ts": 1000.0 + i * 0.002,
            "status_word": 0,
        },
        session_id="test",
    )


def _drain(pub, expected, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if pub._queue is not None and pub._queue.unfinished_tasks == 0:
            break
        time.sleep(0.005)


class TestAsyncPublisher:
    def test_async_publishes_all_frames(self, fake_zmq):
        pub = MeasurementFramePublisher(_make_cfg(async_publish=True))
        pub.start()
        assert pub._writer_thread is not None and pub._writer_thread.is_alive()
        sock = pub._socket
        for i in range(250):
            pub.publish_frames([_frame(i)])
        _drain(pub, 250)
        pub.stop()  # drains + joins before closing the socket
        # 250 frame messages (events none); all on the measurement topic.
        topic = b"rs485.measurement.v1"
        frame_msgs = [m for m in sock.sent if m[0] == topic]
        assert len(frame_msgs) == 250
        assert pub.dropped_records == 0
        assert pub._writer_thread is None
        assert sock.closed

    def test_async_event_routed_through_socket_thread(self, fake_zmq):
        pub = MeasurementFramePublisher(_make_cfg(async_publish=True))
        pub.start()
        sock = pub._socket
        pub.publish_event("connected", port="ttyUSB0")
        _drain(pub, 1)
        pub.stop()
        ev_topic = b"rs485.event.v1"
        assert any(m[0] == ev_topic for m in sock.sent)

    def test_sync_mode_publishes_inline_no_thread(self, fake_zmq):
        pub = MeasurementFramePublisher(_make_cfg(async_publish=False))
        pub.start()
        assert pub._writer_thread is None
        sock = pub._socket
        pub.publish_frames([_frame(i) for i in range(5)])
        topic = b"rs485.measurement.v1"
        assert len([m for m in sock.sent if m[0] == topic]) == 5
        pub.stop()

    def test_start_idempotent_and_stop_twice_safe(self, fake_zmq):
        pub = MeasurementFramePublisher(_make_cfg(async_publish=True))
        pub.start()
        t1 = pub._writer_thread
        pub.start()  # idempotent: socket already set, no second thread spawned
        assert pub._writer_thread is t1
        pub.stop()
        pub.stop()  # safe twice
        assert pub._writer_thread is None
