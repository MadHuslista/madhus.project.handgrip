"""NiceGUI page layout for the LSL Viewer.

This module replaces ``viz/figure.py``'s Matplotlib figure creation.
It builds the browser-rendered page: info panel, 3×2 chart grid,
full-width XY panel, and keyboard / button controls.

Keyboard shortcuts work via NiceGUI's ``ui.keyboard`` — they fire on
browser key events, so OS focus on the viewer window is **not required**.
"""
from __future__ import annotations

import logging
from typing import Any

from nicegui import ui
from omegaconf import DictConfig

from lsl_viewer.types import ViewerState
from lsl_viewer.viz.charts import ChartHandles, clear_chart_data

log = logging.getLogger(__name__)

# Height Tailwind class for the 6 data panels
_PANEL_H = "h-52"
# Height Tailwind class for the XY panel
_XY_H = "h-72"


# ---------------------------------------------------------------------------
# Control callbacks
# ---------------------------------------------------------------------------

def _on_clear(
    state: ViewerState,
    ch: ChartHandles,
    pause_btn: Any | None = None,
) -> None:
    """Handle clear-plots action (key 'c' or button)."""
    clear_chart_data(ch)
    state.live_reset_from_latest_window = True
    state.xy_max_span = {}
    log.info(
        "Manual plot clear requested; buffered samples will be "
        "dropped on next live update."
    )


def _on_pause_toggle(
    state: ViewerState,
    ch: ChartHandles,
    pause_btn: Any,
    is_replay: bool = False,
) -> None:
    """Handle pause/resume (key 'p' or button)."""
    if is_replay:
        state.replay_paused = not state.replay_paused
        pause_btn.set_text(
            "Resume (p)" if state.replay_paused else "Pause (p)"
        )
        log.info("Replay pause toggled: %s", state.replay_paused)
    else:
        state.live_paused = not state.live_paused
        if not state.live_paused:
            clear_chart_data(ch)
            state.live_reset_from_latest_window = True
        pause_btn.set_text(
            "Resume (p)" if state.live_paused else "Pause (p)"
        )
        log.info("Live pause toggled: %s", state.live_paused)


def _on_xy_lock_toggle(state: ViewerState, lock_btn: Any) -> None:
    """Handle XY axis lock-max-span toggle (key 'x' or button)."""
    state.xy_lock_max_span = not state.xy_lock_max_span
    if not state.xy_lock_max_span:
        state.xy_max_span = {}
    lock_btn.set_text(
        "Unlock XY (x)" if state.xy_lock_max_span else "Lock XY (x)"
    )
    log.info("XY max-span lock toggled: %s", state.xy_lock_max_span)


# ---------------------------------------------------------------------------
# Page layout builder
# ---------------------------------------------------------------------------

def build_page_layout(
    cfg: DictConfig,
    ch: ChartHandles,
    state: ViewerState,
    *,
    mode: str = "live",
    is_replay: bool = False,
) -> None:
    """Build the NiceGUI page layout and store ui element references into *ch*.

    Must be called inside a ``@ui.page`` decorated function.

    Side effects
    ------------
    Assigns ``ch.plot_*``, ``ch.info_label`` to the created NiceGUI elements.
    """
    with ui.column().classes("w-full gap-2 p-2"):

        # ── Header ───────────────────────────────────────────────────────
        with ui.row().classes("items-center gap-4"):
            ui.label("LSL Viewer").classes("text-lg font-bold")
            mode_badge = ui.label(f"mode: {mode}").classes(
                "text-sm bg-blue-100 text-blue-800 px-2 py-0.5 rounded"
            )
            if is_replay:
                ui.label("REPLAY").classes(
                    "text-sm bg-orange-100 text-orange-800 px-2 py-0.5 rounded"
                )

        # ── Info panel ────────────────────────────────────────────────────
        ch.info_label = (
            ui.label("Waiting for data…")
            .style(
                "font-family: monospace; font-size: 11px; "
                "white-space: pre; line-height: 1.35; "
                "background: #f8f8f8; padding: 6px 8px; border-radius: 4px; "
                "width: 100%; overflow-x: auto;"
            )
        )

        # ── 3 × 2 chart grid ─────────────────────────────────────────────
        with ui.grid(columns=2).classes("w-full gap-2"):
            ch.plot_target_raw = (
                ui.plotly(ch.fig_target_raw).classes(f"w-full {_PANEL_H}")
            )
            ch.plot_reference_raw = (
                ui.plotly(ch.fig_reference_raw).classes(f"w-full {_PANEL_H}")
            )
            ch.plot_target_filtered = (
                ui.plotly(ch.fig_target_filtered).classes(f"w-full {_PANEL_H}")
            )
            ch.plot_overlay = (
                ui.plotly(ch.fig_overlay).classes(f"w-full {_PANEL_H}")
            )
            ch.plot_target_dt = (
                ui.plotly(ch.fig_target_dt).classes(f"w-full {_PANEL_H}")
            )
            ch.plot_reference_dt = (
                ui.plotly(ch.fig_reference_dt).classes(f"w-full {_PANEL_H}")
            )

        # ── XY panel (full width) ─────────────────────────────────────────
        ch.plot_xy = (
            ui.plotly(ch.fig_xy).classes(f"w-full {_XY_H}")
        )

        # ── Control bar ───────────────────────────────────────────────────
        with ui.row().classes("items-center gap-3 mt-1"):
            clear_btn = ui.button(
                "Clear (c)",
                on_click=lambda: _on_clear(state, ch),
            ).classes("text-xs").props("color=negative outline")

            pause_btn = ui.button(
                "Pause (p)",
            ).classes("text-xs").props("color=primary outline")
            pause_btn.on_click(
                lambda: _on_pause_toggle(state, ch, pause_btn, is_replay=is_replay)
            )

            lock_btn = ui.button(
                "Lock XY (x)",
            ).classes("text-xs").props("color=secondary outline")
            lock_btn.on_click(lambda: _on_xy_lock_toggle(state, lock_btn))

            ui.label("  Keyboard: c=clear  p=pause  x=lock-XY").classes(
                "text-xs text-gray-500 ml-2"
            )

        # ── Keyboard shortcuts ─────────────────────────────────────────────
        def _on_key(e: Any) -> None:
            if getattr(e, "action", None) != "keydown":
                return
            key = getattr(e, "key", "")
            clear_k = str(cfg.viewer.controls.clear_key).strip()
            pause_k = str(cfg.viewer.controls.pause_key).strip()
            xy_k = str(cfg.viewer.xy_correlation.toggle_key).strip()

            if key == clear_k:
                _on_clear(state, ch)
            elif key == pause_k:
                _on_pause_toggle(state, ch, pause_btn, is_replay=is_replay)
            elif key == xy_k:
                _on_xy_lock_toggle(state, lock_btn)

        ui.keyboard(on_key=_on_key)
