"""NiceGUI page builder.

``run_ui_page`` constructs the entire browser-facing UI and registers the
refresh timer.  All UI element handles are passed as closure variables into
the refresh callback (no module-level globals).

Dependency chain: state, ui/refresh, ui/plots, constants, core/ports, core/signals
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from nicegui import ui

from rs485_gui.constants import (
    ACTIVE_SEND_FREQ_CODE_TO_VALUE,
    ACTIVE_SEND_PARSER_PROFILE,
    BAUD_CODE_TO_VALUE,
    COMMAND_METADATA,
)
from rs485_gui.core.ports import enumerate_ports, filter_excluded_ports, get_excluded_serial_ports
from rs485_gui.core.signals import get_plot_signal_key, get_plot_signal_options
from rs485_gui.ui.plots import build_plot_figure
from rs485_gui.ui.refresh import build_refresh_callback

if TYPE_CHECKING:
    from rs485_gui.state import AppState

LOGGER = logging.getLogger(__name__)


## @brief Run ui page.
#
#  @param app_state Parameter description.
#  @param connect_fn Parameter description.
#  @param disconnect_fn Parameter description.
#  @return Result produced by this function.
def run_ui_page(app_state: AppState, *, connect_fn: Any, disconnect_fn: Any) -> None:
    """Construct the NiceGUI page and register the refresh timer.

    *connect_fn* and *disconnect_fn* are callables from ``app.py`` that own
    the session lifecycle.
    """
    cfg = app_state.cfg

    # ---- Theme / title ----
    dark_mode = ui.dark_mode()
    if bool(cfg.ui.light_mode):
        dark_mode.disable()
    else:
        dark_mode.enable()
    ui.page_title(cfg.ui.page_title)

    header = ui.label(cfg.ui.page_title).classes('text-2xl font-bold')
    header.style('padding: 12px 0;')
    status_label = ui.label('Status: Idle').classes('text-sm')

    # ---- Connection panel ----
    with ui.card().classes('w-full'):
        ui.label('Connection').classes('text-lg font-semibold')

        available_ports = filter_excluded_ports(cfg, enumerate_ports(list(cfg.serial.port_hints)))

        with ui.grid(columns=4).classes('w-full gap-4'):
            port_select = ui.select(
                options={p.device: f'{p.device} | {p.description} | {p.hwid}'
                         for p in available_ports},
                value=(
                    app_state.serial_cfg.port
                    if app_state.serial_cfg.port
                    else (available_ports[0].device if available_ports else None)
                ),
                label='Serial port',
            )
            mode_select = ui.select(
                options={
                    'modbus_rtu': 'Modbus RTU (500.AS=0)',
                    'active_send': 'Active send (500.AS=1)',
                },
                value=app_state.mode,
                label='Board mode',
            )
            baud_select = ui.select(
                options={v: f'{v} (code {k})' for k, v in BAUD_CODE_TO_VALUE.items()},
                value=app_state.serial_cfg.baudrate,
                label='Baud rate',
            )
            address_input = ui.number(
                label='Slave address (500.Ar)',
                value=int(app_state.runtime.slave_address),
                min=1, max=253, step=1, format='%.0f',
            )
            parity_select = ui.select(
                options={'N': 'None (502.Vb=0)', 'E': 'Even (502.Vb=1)', 'O': 'Odd (502.Vb=2)'},
                value=app_state.serial_cfg.parity,
                label='Parity',
            )
            stopbits_select = ui.select(
                options={1: '1 stop bit (503.so=1)', 2: '2 stop bits (503.so=2)'},
                value=app_state.serial_cfg.stopbits,
                label='Stop bits',
            )
            active_freq_select = ui.select(
                options={
                    code: f'{freq_hz} Hz (505.AF={code})'
                    for code, freq_hz in ACTIVE_SEND_FREQ_CODE_TO_VALUE.items()
                },
                value=int(app_state.runtime.active_send_frequency_code),
                label='Active-send frequency',
            )
            # Only the supported binary profile is shown
            parser_select = ui.select(
                options={ACTIVE_SEND_PARSER_PROFILE: 'Modbus RTU Response (11 registers)'},
                value=app_state.parse_profile,
                label='Active-send parser profile',
            )

        with ui.row().classes('gap-2 mt-4'):
            ## @brief Refresh port list.
            #
            def refresh_port_list() -> None:
                ports = filter_excluded_ports(
                    cfg, enumerate_ports(list(cfg.serial.port_hints))
                )
                options = {p.device: f'{p.device} | {p.description} | {p.hwid}'
                           for p in ports}
                port_select.options = options
                if options and port_select.value not in options:
                    port_select.value = next(iter(options.keys()))
                port_select.update()
                excluded = get_excluded_serial_ports(cfg)
                suffix = f' (excluded: {excluded})' if excluded else ''
                app_state.push_event(f'Refreshed port list: {len(options)} ports found{suffix}')

            ## @brief Sync form to state.
            #
            def sync_form_to_state() -> None:
                app_state.serial_cfg.port = str(port_select.value or '')
                app_state.serial_cfg.baudrate = int(baud_select.value)
                app_state.serial_cfg.parity = str(parity_select.value)
                app_state.serial_cfg.stopbits = int(stopbits_select.value)
                app_state.mode = str(mode_select.value)
                app_state.parse_profile = str(parser_select.value)
                # Update RuntimeSettings (not DictConfig) for UI-mutable values
                app_state.runtime.slave_address = int(address_input.value)
                app_state.runtime.active_send_frequency_code = int(active_freq_select.value)
                app_state.runtime.plot_signal_key = str(signal_select.value)
                app_state.runtime.clear_plot_on_connect = bool(clear_on_connect_switch.value)
                # Mirror runtime -> cfg for subsystems that read cfg directly
                # (ipc publisher reads cfg.device.slave_address for board_profile snapshot)
                try:
                    cfg.device.slave_address = int(address_input.value)
                    cfg.device.active_send_frequency_code = int(active_freq_select.value)
                    cfg.ui.plot_signal_key = str(signal_select.value)
                    cfg.ui.clear_plot_on_connect = bool(clear_on_connect_switch.value)
                except Exception:
                    pass

            ## @brief On connect.
            #
            def on_connect() -> None:
                sync_form_to_state()
                try:
                    connect_fn()
                except Exception as exc:
                    app_state.status_text = f'Connect failed: {exc}'
                    app_state.push_event(f'Connect failed: {exc}')

            ## @brief On disconnect.
            #
            def on_disconnect() -> None:
                disconnect_fn()
                app_state.push_event('Disconnected by user')

            ui.button('Refresh ports', on_click=refresh_port_list)
            ui.button('Connect', on_click=on_connect)
            ui.button('Disconnect', on_click=on_disconnect)
            connection_badge = ui.badge(app_state.connection_label)

        ui.separator().classes('mt-4 mb-2')
        ui.label(
            'Current effective board-side communication settings you should mirror on the instrument'
        ).classes('text-lg font-semibold')
        board_cfg_preview = ui.textarea(value='', label='Board-side values to mirror').props(
            'readonly'
        ).classes('w-full font-mono')
        board_cfg_preview.style('height: 180px; overflow-y: auto; overflow-x: auto; white-space: pre;')

    # ---- Live signal plot ----
    with ui.card().classes('w-full mt-4'):
        ui.label('Live signal').classes('text-lg font-semibold')
        with ui.row().classes('w-full items-center gap-3 flex-wrap'):
            signal_select = ui.select(
                options=get_plot_signal_options(),
                value=get_plot_signal_key(cfg),
                label='Plotted signal',
            )
            clear_trace_button = ui.button('Clear signal trace')
            clear_on_connect_switch = ui.switch(
                'Clear signal trace on new connection',
                value=bool(cfg.ui.clear_plot_on_connect),
            )
        with ui.row().classes('w-full gap-4 items-start mt-2 no-wrap'):
            with ui.card().classes('w-3/4'):
                plot = ui.plotly(build_plot_figure(app_state)).classes('w-full')
            with ui.column().classes('w-1/4 gap-3'):
                with ui.card().classes('w-full'):
                    ui.label('Measured sampling rate').classes('text-base font-semibold')
                    sampling_rate_label = ui.label('').classes('w-full text-sm')
                    sampling_rate_label.style('white-space: pre-wrap;')
                with ui.expansion('Selected signal info').classes('w-full'):
                    signal_metadata_label = ui.label('').classes('w-full text-xs font-mono')
                    signal_metadata_label.style('white-space: pre-wrap;')

        plot_cache = {'version': -1, 'signal_key': None, 'mode': None}

        ## @brief On signal change.
        #
        def on_signal_change() -> None:
            cfg.ui.plot_signal_key = str(signal_select.value)
            plot_cache['version'] = -1
            plot_cache['signal_key'] = None
            plot.figure = build_plot_figure(app_state)
            plot.update()

        signal_select.on('update:model-value', lambda _e: on_signal_change())
        clear_trace_button.on(
            'click',
            lambda _e: app_state.clear_signal_trace(
                reason='manual clear button', reset_session_counters=False
            ),
        )
        clear_on_connect_switch.on(
            'update:model-value',
            lambda _e: setattr(cfg.ui, 'clear_plot_on_connect', bool(clear_on_connect_switch.value)),
        )

    # ---- Log text areas ----
    with ui.row().classes('w-full gap-4 items-start mt-4 no-wrap'):
        with ui.card().classes('w-1/2'):
            ui.label('Raw transport / raw interpreted').classes('text-lg font-semibold')
            raw_log_area = ui.textarea(value='', label='Raw log').props('readonly').classes(
                'w-full font-mono'
            )
            raw_log_area.style(
                f'height: {cfg.ui.log_height_px}px; overflow-y: auto; '
                'overflow-x: auto; white-space: pre;'
            )
        with ui.card().classes('w-1/2'):
            ui.label('Interpreted data').classes('text-lg font-semibold')
            interpreted_log_area = ui.textarea(value='', label='Interpreted log').props(
                'readonly'
            ).classes('w-full font-mono')
            interpreted_log_area.style(
                f'height: {cfg.ui.log_height_px}px; overflow-y: auto; '
                'overflow-x: auto; white-space: pre;'
            )

    with ui.card().classes('w-full mt-4'):
        ui.label('Event log').classes('text-lg font-semibold')
        event_log_area = ui.textarea(value='', label='Events').props('readonly').classes(
            'w-full font-mono'
        )
        event_log_area.style(
            f'height: {cfg.ui.event_log_height_px}px; overflow-y: auto; '
            'overflow-x: auto; white-space: pre;'
        )

    # ---- Advanced actions (Modbus RTU only) ----
    with ui.expansion('Advanced Actions').classes('w-full mt-4') as advanced_actions_expansion:
        ui.label(
            'These actions write to the command register and are only available '
            'in Modbus RTU mode (500.AS=0).'
        ).classes('text-sm')
        advanced_action_buttons = []
        with ui.column().classes('w-full gap-2'):
            for command_meta in COMMAND_METADATA:
                ## @brief Make handler.
                #
                #  @param name Parameter description.
                #  @return Result produced by this function.
                def _make_handler(name: str) -> Any:
                    ## @brief Handler.
                    #
                    def _handler() -> None:
                        if app_state.transport is None:
                            ui.notify('Not connected')
                            return
                        try:
                            app_state.transport.send_command(name)
                            ui.notify(f'Sent {name}')
                        except Exception as exc:
                            app_state.push_event(f'Command failed: {name} -> {exc}')
                            ui.notify(f'Command failed: {exc}', color='negative')
                    return _handler

                with ui.row().classes('w-full items-start gap-4 no-wrap'):
                    button = ui.button(
                        command_meta['title'], on_click=_make_handler(command_meta['name'])
                    )
                    advanced_action_buttons.append(button)
                    desc = ui.label(
                        f"{command_meta['description']}\n"
                        f"Equivalent manual action: {command_meta['manual_equivalent']}"
                    ).classes('text-sm')
                    desc.style('white-space: pre-wrap;')

    # ---- Register refresh timer ----
    refresh_counter = {'count': 0}
    refresh_ui = build_refresh_callback(
        app_state,
        status_label=status_label,
        connection_badge=connection_badge,
        raw_log_area=raw_log_area,
        interpreted_log_area=interpreted_log_area,
        event_log_area=event_log_area,
        plot=plot,
        sampling_rate_label=sampling_rate_label,
        signal_metadata_label=signal_metadata_label,
        board_cfg_preview=board_cfg_preview,
        signal_select=signal_select,
        mode_select=mode_select,
        baud_select=baud_select,
        address_input=address_input,
        parity_select=parity_select,
        stopbits_select=stopbits_select,
        active_freq_select=active_freq_select,
        advanced_actions_expansion=advanced_actions_expansion,
        advanced_action_buttons=advanced_action_buttons,
        plot_cache=plot_cache,
        refresh_counter=refresh_counter,
    )
    ui.timer(interval=float(cfg.ui.refresh_interval_s), callback=refresh_ui)
