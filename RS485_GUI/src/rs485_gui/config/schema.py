"""Hydra structured config schema for rs485_gui.

These dataclasses define the complete schema with all default values.  They
are used for *documentation and validation only* — the Hydra global runtime
is NOT initialised (see loader.py for the reason).

Instantiating ``Rs485GuiConfig()`` gives a fully populated default config
that matches the intent of ``config/config.yaml``.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
# @brief Represents the SessionConfig component.
class SessionConfig:
    #: Optional calibration session id propagated to logs and IPC.
    #: Set only when you want GUI logs/IPC to carry a specific recording session id.
    session_id: str | None = None


@dataclass
# @brief Represents the AppConfig component.
class AppConfig:
    log_level: str = "INFO"
    worker_join_timeout_s: float = 1.5


@dataclass
# @brief Represents the UiConfig component.
class UiConfig:
    page_title: str = "High-Speed Acquisition Instrument GUI"
    host: str = "127.0.0.1"
    port: int = 8088
    refresh_interval_s: float = 0.1
    plot_height_px: int = 360
    log_height_px: int = 380
    event_log_height_px: int = 180
    visible_log_entries: int = 40
    visible_event_entries: int = 120
    max_retained_log_entries: int = 160
    max_retained_event_entries: int = 500
    max_plot_points: int = 3000
    max_render_plot_points: int = 700
    default_plot_signal_key: str = "net_value"
    plot_signal_key: str = "net_value"
    clear_plot_on_connect: bool = True
    sampling_rate_window_samples: int = 5000
    sampling_rate_outlier_low_ratio: float = 0.25
    sampling_rate_outlier_high_ratio: float = 4.0
    sampling_rate_outlier_min_samples: int = 16
    max_signal_samples_per_second: float = 0.0
    display_max_samples_per_second: float = 30.0
    active_send_render_downsample_factor: int = 2
    modbus_rtu_render_downsample_factor: int = 1
    max_ui_entry_chars: int = 300
    max_log_textarea_chars: int = 30000
    max_event_textarea_chars: int = 20000
    plot_update_every_n_refreshes: int = 1
    log_update_every_n_refreshes: int = 5
    sampling_update_every_n_refreshes: int = 5
    metadata_update_every_n_refreshes: int = 10
    board_config_update_every_n_refreshes: int = 10
    controls_update_every_n_refreshes: int = 10
    plot_skip_if_unchanged: bool = True
    plot_trace_type: str = "scattergl"
    light_mode: bool = True


@dataclass
# @brief Represents the LoggerConfig component.
class LoggerConfig:
    enabled: bool = True
    directory: str = "./logs"
    write_mode: str = "overwrite"
    raw_signal_filename: str = "raw_signal.ndjson"
    interpreted_signal_filename: str = "interpreted_signal.ndjson"
    gui_signal_filename: str = "gui_signal.csv"
    debug_log_to_file: bool = True
    debug_log_filename: str = "acquisition_debug.log"
    event_log_filename: str = "event.log"
    flush_every_n_batches: int = 25
    flush_interval_s: float = 1.0


@dataclass
# @brief Represents the IpcConfig component.
class IpcConfig:
    enabled: bool = True
    transport: str = "zmq_pub"
    bind: str = "tcp://127.0.0.1:5557"
    topic: str = "rs485.measurement.v1"
    event_topic: str = "rs485.event.v1"
    signal_key: str = "net_value"
    send_hwm: int = 2000
    linger_ms: int = 0
    drop_on_backpressure: bool = True
    start_on_app_launch: bool = False
    start_on_connect: bool = True
    stop_on_disconnect: bool = True
    require_pylsl_clock: bool = True
    publish_after_max_rate_filter: bool = False
    log_every_s: float = 5.0


@dataclass
# @brief Represents the SerialConfig component.
class SerialConfig:
    default_port: str = ""
    excluded_ports: list[str] = field(default_factory=list)
    default_baudrate: int = 460800
    default_parity: str = "N"
    default_stopbits: int = 1
    bytesize: int = 8
    timeout_s: float = 0.2
    inter_frame_gap_s: float = 0.001
    port_hints: list[str] = field(
        default_factory=lambda: [
            "USB",
            "RS485",
            "FTDI",
            "CH340",
            "CP210",
            "PL2303",
            "ttyUSB",
            "ttyACM",
        ]
    )


@dataclass
# @brief Represents the DeviceConfig component.
class DeviceConfig:
    mode: str = "active_send"
    slave_address: int = 1
    active_send_frequency_code: int = 8
    poll_interval_s: float = 0.001
    error_backoff_s: float = 0.25
    #: Promoted from hardcoded constant; allows alternate register-map firmware.
    read_start_register: int = 0
    read_register_count: int = 11
    command_register: int = 11


@dataclass
# @brief Represents the ActiveSendConfig component.
class ActiveSendConfig:
    timestamp_policy: str = "batch_end_anchored"
    default_parser_profile: str = "modbus_rtu_response_11regs"
    default_numeric_index: int = 0
    default_hex_word_endianness: str = "big"
    read_timeout_s: float = 0.5
    delivery_window_s: float = 0.010
    max_frames_per_delivery: int = 16
    read_chunk_bytes: int = 1024
    max_read_bytes_per_cycle: int = 8192
    clock_reanchor_max_drift_s: float = 0.050
    log_monotonic_adjust_warn_s: float = 0.005
    max_chain_lead_s: float = 0.050
    measured_rate_enabled: bool = True
    measured_rate_window_s: float = 2.0
    measured_rate_ewma_alpha: float = 0.25
    measured_rate_max_dev_frac: float = 0.01
    recovery_enabled: bool = True
    recovery_warning_threshold: int = 48
    recovery_min_interval_s: float = 1.0
    recovery_reset_input_buffer: bool = True
    max_binary_frame_bytes: int = 64
    max_buffer_bytes: int = 8192
    frame_slave_id: int = 1
    frame_function_code: int = 3
    frame_register_count: int = 11
    log_first_n_good_frames: int = 5
    log_summary_every_n_good_frames: int = 250
    log_bad_frame_hex_bytes: int = 64
    warning_emit_interval_s: float = 5.0
    detailed_warning_limit: int = 2


@dataclass
# @brief Represents the LoggingConfig component.
class LoggingConfig:
    """Per-module log level overrides (new in v0.2 refactor).

    ``root_level`` is an alias for ``app.log_level``; either may be used.
    ``module_levels`` maps logger names to level strings (DEBUG/INFO/WARNING/ERROR/CRITICAL).

    Example in config.yaml::

        logging:
          root_level: INFO
          module_levels:
            rs485_gui.transport.active_send: DEBUG
            rs485_gui.io.publisher: WARNING
    """

    root_level: str = "INFO"
    module_levels: dict = field(default_factory=dict)


@dataclass
# @brief Represents the Rs485GuiConfig component.
class Rs485GuiConfig:
    """Root structured config for rs485_gui.

    Used for schema documentation and validation.  The Hydra global runtime
    is NOT initialised — ``@hydra.main`` is explicitly avoided because NiceGUI
    re-executes the module when serving the root page, which would trigger a
    ``GlobalHydra`` re-initialisation crash on the second execution.
    """

    session: SessionConfig = field(default_factory=SessionConfig)
    app: AppConfig = field(default_factory=AppConfig)
    ui: UiConfig = field(default_factory=UiConfig)
    logger: LoggerConfig = field(default_factory=LoggerConfig)
    ipc: IpcConfig = field(default_factory=IpcConfig)
    serial: SerialConfig = field(default_factory=SerialConfig)
    device: DeviceConfig = field(default_factory=DeviceConfig)
    active_send: ActiveSendConfig = field(default_factory=ActiveSendConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
