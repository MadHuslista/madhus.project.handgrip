"""Acquisition worker thread.

Runs in a daemon thread started by ``connect_state()``.  Continuously calls
``transport.read_frames()``, applies rate limiting, dispatches to IPC and file
logger at full rate, and pushes display-throttled frames to ``AppState``.

Dependency chain: state (which brings in all subsystems)
"""
from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rs485_gui.state import AppState

LOGGER = logging.getLogger(__name__)


def acquisition_worker(app_state: AppState) -> None:
    """Main loop executed by the acquisition worker thread.

    The loop runs until ``app_state.stop_event`` is set.
    """
    assert app_state.transport is not None, 'Transport must be set before starting worker'

    poll_interval_s = max(0.0, float(app_state.cfg.device.poll_interval_s))
    next_poll_deadline = time.perf_counter()
    app_state.push_event(
        f'Worker started in mode={app_state.mode} parser={app_state.parse_profile}'
    )

    while not app_state.stop_event.is_set():
        try:
            if app_state.mode == 'modbus_rtu' and poll_interval_s > 0:
                now = time.perf_counter()
                if now < next_poll_deadline:
                    time.sleep(next_poll_deadline - now)
            cycle_start = time.perf_counter()

            frames = app_state.transport.read_frames()

            # Publish at full rate (before any rate limiting) when configured
            if app_state.ipc_publisher is not None and not bool(
                app_state.cfg.ipc.publish_after_max_rate_filter
            ):
                app_state.ipc_publisher.publish_frames(frames)

            if not frames:
                if app_state.mode == 'modbus_rtu' and poll_interval_s > 0:
                    next_poll_deadline = cycle_start + poll_interval_s
                continue

            # Apply acquisition max-rate filter (file log + IPC use this output)
            acquisition_frames = app_state.filter_frames_by_max_sampling_rate(frames)
            if not acquisition_frames:
                app_state.status_text = (
                    f'Connected: batch filtered by acquisition max signal rate '
                    f'(received={len(frames)}, '
                    f'dropped_total={app_state.sampling_stats.dropped_samples_max_rate})'
                )
                if app_state.mode == 'modbus_rtu' and poll_interval_s > 0:
                    next_poll_deadline = cycle_start + poll_interval_s
                continue

            # Optionally publish after rate limiting
            if app_state.ipc_publisher is not None and bool(
                app_state.cfg.ipc.publish_after_max_rate_filter
            ):
                app_state.ipc_publisher.publish_frames(acquisition_frames)

            # File logging at full acquisition rate
            if app_state.signal_logger is not None:
                app_state.signal_logger.write_frames(acquisition_frames)

            # Record acquisition timing (authoritative sampling rate measurement)
            app_state.record_acquisition_frames(acquisition_frames)

            # Throttle for UI display
            ui_frames = app_state.filter_frames_for_ui(acquisition_frames)
            if ui_frames:
                app_state.push_frames(ui_frames)

            last_frame = acquisition_frames[-1]
            app_state.status_text = (
                f'Connected: last frame at {last_frame.host_ts_iso} '
                f'(ipc/log={len(acquisition_frames)}/{len(frames)}, '
                f'ui={len(ui_frames)}/{len(acquisition_frames)})'
            )

            if app_state.mode == 'modbus_rtu' and poll_interval_s > 0:
                next_poll_deadline = cycle_start + poll_interval_s

        except TimeoutError as exc:
            app_state.status_text = f'Waiting for data: {exc}'
            if app_state.mode == 'modbus_rtu' and poll_interval_s > 0:
                next_poll_deadline = time.perf_counter() + poll_interval_s

        except Exception as exc:  # pragma: no cover — runtime guard
            app_state.status_text = f'Acquisition error: {exc}'
            app_state.push_event(f'Acquisition error: {exc}')
            LOGGER.exception('Unhandled exception in acquisition worker')
            if app_state.mode == 'modbus_rtu' and poll_interval_s > 0:
                next_poll_deadline = time.perf_counter() + poll_interval_s
            time.sleep(float(app_state.cfg.device.error_backoff_s))

    app_state.push_event('Worker stopped')
