"""Application entry point.

``run_app`` wires all subsystems together and starts the NiceGUI server.
``main`` is the CLI entry point registered in ``pyproject.toml``.

NiceGUI re-execution note
-------------------------
NiceGUI re-executes this module when serving the root page or a 404
fallback.  The os.environ guard used in the original monolith has been replaced by the idempotent
``configure_logging`` guard in ``config/loader.py`` (checks
``root.handlers``).  The config is loaded fresh on each execution but
``configure_logging`` is a no-op after the first call.
"""
from __future__ import annotations

import logging
import os
import threading
from collections import deque

from nicegui import app as nicegui_app
from nicegui import ui
from omegaconf import DictConfig

from rs485_gui.config.loader import load_app_config
from rs485_gui.core.ports import (
    get_excluded_serial_ports,
    is_serial_port_excluded,
)
from rs485_gui.io.logger import SignalFileLogger
from rs485_gui.io.publisher import MeasurementFramePublisher
from rs485_gui.models import SerialSettings
from rs485_gui.state import AppState, RuntimeSettings
from rs485_gui.transport.active_send import ActiveSendBoardTransport
from rs485_gui.transport.modbus import ModbusBoardTransport
from rs485_gui.ui.layout import run_ui_page
from rs485_gui.worker import acquisition_worker

LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Session lifecycle helpers
# ---------------------------------------------------------------------------

def _cfg_to_serial_settings(cfg: DictConfig) -> SerialSettings:
    return SerialSettings(
        port=str(cfg.serial.default_port),
        baudrate=int(cfg.serial.default_baudrate),
        bytesize=int(cfg.serial.bytesize),
        parity=str(cfg.serial.default_parity),
        stopbits=int(cfg.serial.default_stopbits),
        timeout=float(cfg.serial.timeout_s),
    )


def disconnect_state(app_state: AppState) -> None:
    """Tear down the active acquisition session cleanly."""
    if app_state.ipc_publisher is not None:
        app_state.ipc_publisher.publish_event(
            'serial_disconnect_requested',
            port=app_state.serial_cfg.port,
            mode=app_state.mode,
        )
    app_state.stop_event.set()
    if app_state.worker_thread and app_state.worker_thread.is_alive():
        app_state.worker_thread.join(
            timeout=float(app_state.cfg.app.worker_join_timeout_s)
        )
    if app_state.transport is not None:
        try:
            app_state.transport.disconnect()
        except Exception:
            LOGGER.warning('Transport disconnect cleanup warning', exc_info=True)
    app_state.transport = None
    app_state.worker_thread = None
    if app_state.ipc_publisher is not None and bool(
        app_state.cfg.ipc.stop_on_disconnect
    ):
        app_state.ipc_publisher.stop()
    app_state.connected = False
    app_state.connection_label = 'DISCONNECTED'
    app_state.status_text = 'Idle'
    if app_state.signal_logger is not None:
        app_state.signal_logger.close()


def connect_state(app_state: AppState) -> None:
    """Start a new acquisition session."""
    selected_port = str(app_state.serial_cfg.port or '')
    if is_serial_port_excluded(app_state.cfg, selected_port):
        excluded = ', '.join(get_excluded_serial_ports(app_state.cfg))
        raise RuntimeError(
            f'Serial port {selected_port} is reserved/excluded for another process. '
            f'Configured excluded_ports=[{excluded}]. Select the RS485 board port instead.'
        )

    disconnect_state(app_state)
    app_state.stop_event = threading.Event()

    window_size = int(app_state.cfg.ui.sampling_rate_window_samples)
    app_state.sampling_stats.reset_all(window_size)
    app_state.display_sampling_stats.reset_all(window_size)
    app_state._last_max_rate_frame_ts = None

    if bool(app_state.cfg.ui.clear_plot_on_connect):
        app_state.clear_signal_trace(reason='new connection', reset_session_counters=True)
    else:
        app_state.sampling_stats.reset_all(window_size)
        app_state.display_sampling_stats.reset_all(window_size)
        app_state._last_max_rate_frame_ts = None

    mode = app_state.mode
    if mode == 'modbus_rtu':
        app_state.transport = ModbusBoardTransport(app_state)
    else:
        app_state.transport = ActiveSendBoardTransport(app_state)

    # Sync runtime slave address into cfg so board_profile_snapshot picks it up
    try:
        app_state.cfg.device.slave_address = int(app_state.runtime.slave_address)
        app_state.cfg.device.active_send_frequency_code = int(
            app_state.runtime.active_send_frequency_code
        )
    except Exception:
        pass

    try:
        if app_state.signal_logger is not None:
            app_state.signal_logger.open()
        app_state.transport.connect()
        if bool(app_state.cfg.ipc.enabled) and bool(app_state.cfg.ipc.start_on_connect):
            _start_ipc_publisher(app_state)
            if app_state.ipc_publisher is not None:
                app_state.ipc_publisher.publish_event(
                    'serial_connected',
                    port=app_state.serial_cfg.port,
                    mode=app_state.mode,
                )
    except Exception:
        if app_state.ipc_publisher is not None and bool(
            app_state.cfg.ipc.stop_on_disconnect
        ):
            app_state.ipc_publisher.stop()
        if app_state.transport is not None:
            try:
                app_state.transport.disconnect()
            except Exception:
                LOGGER.warning('Connect cleanup error', exc_info=True)
        if app_state.signal_logger is not None:
            app_state.signal_logger.close()
        app_state.transport = None
        raise

    app_state.worker_thread = threading.Thread(
        target=acquisition_worker,
        args=(app_state,),
        daemon=True,
        name='acquisition-worker',
    )
    app_state.worker_thread.start()
    app_state.connected = True
    app_state.connection_label = 'CONNECTED'
    app_state.status_text = f'Connected on {app_state.serial_cfg.port}'
    app_state.push_event(
        f'Connected to {app_state.serial_cfg.port} '
        f'baud={app_state.serial_cfg.baudrate} '
        f'parity={app_state.serial_cfg.parity} '
        f'stopbits={app_state.serial_cfg.stopbits} '
        f'mode={mode}'
    )
    if mode == 'active_send':
        cfg = app_state.cfg
        app_state.push_event(
            'Active-send decoder config: '
            f'parser={app_state.parse_profile} '
            f'chunk_bytes={int(cfg.active_send.read_chunk_bytes)} '
            f'max_read_bytes_per_cycle={int(cfg.active_send.max_read_bytes_per_cycle)} '
            f'delivery_window_s={float(cfg.active_send.delivery_window_s)} '
            f'max_frames_per_delivery={int(cfg.active_send.max_frames_per_delivery)} '
            f'timeout_s={float(cfg.active_send.read_timeout_s)} '
            f'frame_slave_id={int(cfg.active_send.frame_slave_id) or int(cfg.device.slave_address)} '
            f'function=0x{int(cfg.active_send.frame_function_code):02X} '
            f'registers={int(cfg.active_send.frame_register_count)}'
        )
    if app_state.signal_logger is not None and app_state.signal_logger.enabled:
        cfg = app_state.cfg
        debug_log_path: str | None = None
        if bool(cfg.logger.debug_log_to_file):
            debug_log_path = str(
                (app_state.signal_logger.directory / str(cfg.logger.debug_log_filename)).resolve()
            )
        app_state.push_event(
            'Logger paths: '
            f'raw={app_state.signal_logger.raw_path.resolve()} | '
            f'interpreted={app_state.signal_logger.interpreted_path.resolve()} | '
            f'gui={app_state.signal_logger.gui_path.resolve()} | '
            f'events={app_state.signal_logger.event_path.resolve()}'
            + (f' | debug={debug_log_path}' if debug_log_path else '')
        )


def _start_ipc_publisher(app_state: AppState) -> None:
    """Bind the IPC ZMQ endpoint; create the publisher object if needed."""
    if not bool(app_state.cfg.ipc.enabled):
        return
    if app_state.ipc_publisher is None:
        pub = MeasurementFramePublisher(app_state.cfg)
        pub.session_id = app_state.get_session_id()
        pub.board_profile = app_state.build_board_profile_snapshot()
        app_state.ipc_publisher = pub
    else:
        app_state.ipc_publisher.session_id = app_state.get_session_id()
        app_state.ipc_publisher.board_profile = app_state.build_board_profile_snapshot()
    app_state.ipc_publisher.start()
    app_state.push_event(
        f'RS485 IPC publisher active: bind={app_state.cfg.ipc.bind} '
        f'topic={app_state.cfg.ipc.topic} '
        f'signal_key={app_state.cfg.ipc.signal_key}'
    )


# ---------------------------------------------------------------------------
# Main application runner
# ---------------------------------------------------------------------------

def run_app(cfg: DictConfig) -> None:
    """Wire all subsystems and start the NiceGUI server."""
    # Log config once per process (env-var guard replaced by idempotent
    # configure_logging() handler check in loader.py)
    if os.environ.get('_RS485_GUI_CONFIG_LOGGED') != '1':
        LOGGER.info('Loaded config:\n%s', __import__('omegaconf').OmegaConf.to_yaml(cfg))
        os.environ['_RS485_GUI_CONFIG_LOGGED'] = '1'

    signal_logger = SignalFileLogger(cfg)

    app_state = AppState(
        cfg=cfg,
        serial_cfg=_cfg_to_serial_settings(cfg),
        mode=str(cfg.device.mode),
        runtime=RuntimeSettings(
            slave_address=int(cfg.device.slave_address),
            active_send_frequency_code=int(cfg.device.active_send_frequency_code),
            plot_signal_key=str(cfg.ui.plot_signal_key),
            clear_plot_on_connect=bool(cfg.ui.clear_plot_on_connect),
        ),
        raw_log=deque(maxlen=int(cfg.ui.max_retained_log_entries)),
        interpreted_log=deque(maxlen=int(cfg.ui.max_retained_log_entries)),
        event_log=deque(maxlen=int(cfg.ui.max_retained_event_entries)),
        frame_history=deque(maxlen=int(cfg.ui.max_plot_points)),
        parse_profile=str(cfg.active_send.default_parser_profile),
        signal_logger=signal_logger,
    )

    # Optionally create IPC publisher object (does not bind yet)
    if bool(cfg.ipc.enabled):
        pub = MeasurementFramePublisher(cfg)
        pub.session_id = app_state.get_session_id()
        pub.board_profile = app_state.build_board_profile_snapshot()
        app_state.ipc_publisher = pub
        if bool(cfg.ipc.start_on_app_launch):
            try:
                pub.start()
                app_state.push_event(
                    f'RS485 IPC publisher enabled at app launch: '
                    f'bind={cfg.ipc.bind} topic={cfg.ipc.topic} '
                    f'signal_key={cfg.ipc.signal_key}'
                )
            except Exception as exc:
                LOGGER.warning('RS485 IPC publisher did not start at app launch: %s', exc)
                app_state.push_event(f'RS485 IPC publisher start warning: {exc}')
        else:
            app_state.push_event(
                f'RS485 IPC publisher configured; it will bind on Connect: '
                f'bind={cfg.ipc.bind} topic={cfg.ipc.topic} '
                f'signal_key={cfg.ipc.signal_key}'
            )

    def cleanup() -> None:
        disconnect_state(app_state)
        if app_state.ipc_publisher is not None:
            app_state.ipc_publisher.stop()

    nicegui_app.on_shutdown(cleanup)

    run_ui_page(
        app_state,
        connect_fn=lambda: connect_state(app_state),
        disconnect_fn=lambda: disconnect_state(app_state),
    )

    try:
        ui.run(
            host=str(cfg.ui.host),
            port=int(cfg.ui.port),
            reload=False,
            title=str(cfg.ui.page_title),
        )
    except KeyboardInterrupt:
        LOGGER.info('Stopping on user request (KeyboardInterrupt)')
    finally:
        cleanup()


def main() -> None:
    """CLI entry point registered in ``pyproject.toml``."""
    cfg = load_app_config()
    run_app(cfg)
