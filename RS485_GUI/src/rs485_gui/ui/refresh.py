"""UI refresh timer callback.

``build_refresh_callback`` returns a closure that NiceGUI calls on every
timer tick.  It reads from ``AppState`` (under locks where needed) and
pushes updates to the pre-built UI element references.

All NiceGUI element handles are captured via closure — no globals.

Dependency chain: state, ui/plots, core/signals, core/sampling, constants
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from rs485_gui.constants import ACTIVE_SEND_FREQ_CODE_TO_VALUE, BAUD_CODE_TO_VALUE
from rs485_gui.core.codec import build_log_text
from rs485_gui.core.signals import (
    build_signal_metadata_text,
    format_rate,
    get_plot_signal_key,
    get_target_sampling_rate_hz,
)
from rs485_gui.ui.plots import build_plot_figure

if TYPE_CHECKING:
    from rs485_gui.state import AppState

LOGGER = logging.getLogger(__name__)


## @brief Build refresh callback.
#
#  @param app_state Parameter description.
#  @param status_label Parameter description.
#  @param connection_badge Parameter description.
#  @param raw_log_area Parameter description.
#  @param interpreted_log_area Parameter description.
#  @param event_log_area Parameter description.
#  @param plot Parameter description.
#  @param sampling_rate_label Parameter description.
#  @param signal_metadata_label Parameter description.
#  @param board_cfg_preview Parameter description.
#  @param signal_select Parameter description.
#  @param mode_select Parameter description.
#  @param baud_select Parameter description.
#  @param address_input Parameter description.
#  @param parity_select Parameter description.
#  @param stopbits_select Parameter description.
#  @param active_freq_select Parameter description.
#  @param advanced_actions_expansion Parameter description.
#  @param advanced_action_buttons Parameter description.
#  @param plot_cache Parameter description.
#  @param refresh_counter Parameter description.
#  @return Constructed object for this operation.
def build_refresh_callback(
    app_state: AppState,
    *,
    status_label: Any,
    connection_badge: Any,
    raw_log_area: Any,
    interpreted_log_area: Any,
    event_log_area: Any,
    plot: Any,
    sampling_rate_label: Any,
    signal_metadata_label: Any,
    board_cfg_preview: Any,
    signal_select: Any,
    mode_select: Any,
    baud_select: Any,
    address_input: Any,
    parity_select: Any,
    stopbits_select: Any,
    active_freq_select: Any,
    advanced_actions_expansion: Any,
    advanced_action_buttons: list[Any],
    plot_cache: dict[str, Any],
    refresh_counter: dict[str, int],
) -> Any:
    """Return the ``refresh_ui`` closure for the NiceGUI timer."""

    cfg = app_state.cfg

    ## @brief Refresh ui.
    #
    def refresh_ui() -> None:
        refresh_counter['count'] += 1
        count = refresh_counter['count']

        # ---- Status / connection badge ----
        status_text = f'Status: {app_state.status_text}'
        if status_label.text != status_text:
            status_label.text = status_text
            status_label.update()
        if connection_badge.text != app_state.connection_label:
            connection_badge.text = app_state.connection_label
            connection_badge.update()

        visible_log = int(cfg.ui.visible_log_entries)
        visible_event = int(cfg.ui.visible_event_entries)
        max_log_chars = int(cfg.ui.max_log_textarea_chars)
        max_event_chars = int(cfg.ui.max_event_textarea_chars)

        # ---- Log text areas ----
        log_stride = max(1, int(cfg.ui.log_update_every_n_refreshes))
        if (count % log_stride) == 0:
            raw_items = list(app_state.raw_log)[:visible_log] if visible_log > 0 else list(app_state.raw_log)
            interp_items = list(app_state.interpreted_log)[:visible_log] if visible_log > 0 else list(app_state.interpreted_log)
            event_items = list(app_state.event_log)[:visible_event] if visible_event > 0 else list(app_state.event_log)

            raw_text = build_log_text(raw_items, '\n', max_log_chars)
            interp_text = build_log_text(interp_items, '\n', max_log_chars)
            event_text = build_log_text(event_items, '\n', max_event_chars)

            if raw_log_area.value != raw_text:
                raw_log_area.value = raw_text
                raw_log_area.update()
            if interpreted_log_area.value != interp_text:
                interpreted_log_area.value = interp_text
                interpreted_log_area.update()
            if event_log_area.value != event_text:
                event_log_area.value = event_text
                event_log_area.update()

        # ---- Plot ----
        plot_stride = max(1, int(cfg.ui.plot_update_every_n_refreshes))
        current_signal_key = get_plot_signal_key(cfg)
        if signal_select.value != current_signal_key:
            signal_select.value = current_signal_key
            signal_select.update()
        if (count % plot_stride) == 0:
            with app_state.frame_lock:
                current_version = int(app_state.frame_history_version)
            current_mode = app_state.mode
            skip_unchanged = bool(cfg.ui.plot_skip_if_unchanged)
            if (
                not skip_unchanged
                or current_version != plot_cache['version']
                or current_signal_key != plot_cache['signal_key']
                or current_mode != plot_cache['mode']
            ):
                plot.figure = build_plot_figure(app_state)
                plot.update()
                plot_cache['version'] = current_version
                plot_cache['signal_key'] = current_signal_key
                plot_cache['mode'] = current_mode

        # ---- Sampling rate ----
        sampling_stride = max(1, int(cfg.ui.sampling_update_every_n_refreshes))
        if (count % sampling_stride) == 0:
            target_hz = get_target_sampling_rate_hz(cfg, str(mode_select.value))
            max_hz = float(cfg.ui.max_signal_samples_per_second or 0.0)
            display_max_hz = float(cfg.ui.display_max_samples_per_second or 0.0)
            mean_hz, std_hz, window_count, received_count, dropped_count = (
                app_state.sampling_stats.snapshot(
                    outlier_low_ratio=float(cfg.ui.sampling_rate_outlier_low_ratio),
                    outlier_high_ratio=float(cfg.ui.sampling_rate_outlier_high_ratio),
                    outlier_min_samples=int(cfg.ui.sampling_rate_outlier_min_samples),
                )
            )
            display_mean_hz, display_std_hz, display_window_count, _, _ = (
                app_state.display_sampling_stats.snapshot(
                    outlier_low_ratio=float(cfg.ui.sampling_rate_outlier_low_ratio),
                    outlier_high_ratio=float(cfg.ui.sampling_rate_outlier_high_ratio),
                    outlier_min_samples=int(cfg.ui.sampling_rate_outlier_min_samples),
                )
            )
            sampling_text = (
                f'Target acquisition rate: {format_rate(target_hz)}\n'
                f'Measured acquisition mean: {format_rate(mean_hz)}\n'
                f'Measured acquisition std-dev: {format_rate(std_hz)}\n'
                f'Acquisition window: last {window_count} intervals / '
                f'configured {int(cfg.ui.sampling_rate_window_samples)}\n'
                f'Frames received from transport: {received_count}\n'
                f'Frames dropped by acquisition max-rate limiter: {dropped_count}\n'
                f'Configured max processed acquisition rate: {format_rate(max_hz)}\n'
                f'Display/render mean: {format_rate(display_mean_hz)}\n'
                f'Display/render std-dev: {format_rate(display_std_hz)}\n'
                f'Display window: last {display_window_count} intervals; '
                f'display limiter: {format_rate(display_max_hz)}'
            )
            if sampling_rate_label.text != sampling_text:
                sampling_rate_label.text = sampling_text
                sampling_rate_label.update()

        # ---- Signal metadata ----
        metadata_stride = max(1, int(cfg.ui.metadata_update_every_n_refreshes))
        if (count % metadata_stride) == 0:
            with app_state.frame_lock:
                latest_frame = app_state.latest_frame
                frame_history = list(app_state.frame_history)
            signal_metadata_text = build_signal_metadata_text(
                latest_frame, frame_history, cfg
            )
            if signal_metadata_label.text != signal_metadata_text:
                signal_metadata_label.text = signal_metadata_text
                signal_metadata_label.update()

        # ---- Board config preview ----
        board_stride = max(1, int(cfg.ui.board_config_update_every_n_refreshes))
        if (count % board_stride) == 0:
            baud_code = next(
                (k for k, v in BAUD_CODE_TO_VALUE.items() if v == int(baud_select.value)), None
            )
            parity_code = {'N': 0, 'E': 1, 'O': 2}.get(str(parity_select.value), '?')
            stop_code = int(stopbits_select.value)
            active_code = int(active_freq_select.value)
            board_cfg_text = (
                f'500.Ar = {int(address_input.value)}\n'
                f'501.br = {baud_code}  # {int(baud_select.value)} bps\n'
                f'502.Vb = {parity_code}  # {parity_select.value}\n'
                f'503.so = {stop_code}\n'
                f'504.AS = {0 if str(mode_select.value) == "modbus_rtu" else 1}\n'
                f'505.AF = {active_code}  # {ACTIVE_SEND_FREQ_CODE_TO_VALUE[active_code]} Hz\n'
            )
            if board_cfg_preview.value != board_cfg_text:
                board_cfg_preview.value = board_cfg_text
                board_cfg_preview.update()

        # ---- Controls enable/disable ----
        controls_stride = max(1, int(cfg.ui.controls_update_every_n_refreshes))
        if (count % controls_stride) == 0:
            advanced_enabled = str(mode_select.value) == 'modbus_rtu'
            try:
                if advanced_enabled:
                    advanced_actions_expansion.enable()
                else:
                    advanced_actions_expansion.disable()
            except Exception:
                pass
            for button in advanced_action_buttons:
                try:
                    if advanced_enabled and app_state.connected:
                        button.enable()
                    else:
                        button.disable()
                except Exception:
                    pass

    return refresh_ui
