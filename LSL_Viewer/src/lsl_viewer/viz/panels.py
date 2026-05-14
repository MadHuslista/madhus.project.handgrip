"""NiceGUI page layout for the LSL Viewer.

Builds the browser-rendered page: info panel, 3×2 time-series grid,
full-width XY scatter panel, and keyboard/button controls.

Changes from v0.3.0 (Plotly → ECharts)
----------------------------------------
* ``ui.plotly(ch.fig_*)`` replaced with ``ui.echart(ch.opts_*)``.
* Handle attributes renamed ``plot_*`` → ``chart_*`` to match the
  ``ChartHandles`` dataclass in ``viz/charts.py``.
* All control callbacks and keyboard handling are unchanged.

Keyboard shortcuts fire on browser key events via ``ui.keyboard`` —
OS focus on the viewer window is **never required**.
"""

from __future__ import annotations

import logging
from typing import Any

from nicegui import ui
from omegaconf import DictConfig

from lsl_viewer.types import ViewerState
from lsl_viewer.viz.charts import ChartHandles, bind_chart_element, clear_chart_data

log = logging.getLogger(__name__)

# Tailwind height classes
_PANEL_H = "h-80"  # 6 time-domain panels
_XY_H = "h-150"  # XY scatter (slightly taller for aspect ratio)


# ---------------------------------------------------------------------------
# Control callbacks  (unchanged from v0.3.0)
# ---------------------------------------------------------------------------


def _on_clear(state: ViewerState, ch: ChartHandles) -> None:
    """Clear plots and arm the post-clear cutoff (key 'c' or button)."""
    clear_chart_data(ch)
    state.live_reset_from_latest_window = True
    state.xy_max_span = {}
    log.info("Manual plot clear; buffered samples will be dropped on next update.")


def _on_pause_toggle(
    state: ViewerState,
    ch: ChartHandles,
    pause_btn: Any,
    is_replay: bool = False,
) -> None:
    """Toggle pause/resume (key 'p' or button)."""
    if is_replay:
        state.replay_paused = not state.replay_paused
        pause_btn.set_text("Resume (p)" if state.replay_paused else "Pause (p)")
        log.info("Replay pause toggled: %s", state.replay_paused)
    else:
        state.live_paused = not state.live_paused
        if not state.live_paused:
            clear_chart_data(ch)
            state.live_reset_from_latest_window = True
        pause_btn.set_text("Resume (p)" if state.live_paused else "Pause (p)")
        log.info("Live pause toggled: %s", state.live_paused)


def _on_xy_lock_toggle(state: ViewerState, lock_btn: Any) -> None:
    """Toggle XY axis lock-max-span (key 'x' or button)."""
    state.xy_lock_max_span = not state.xy_lock_max_span
    if not state.xy_lock_max_span:
        state.xy_max_span = {}
    lock_btn.set_text("Unlock XY (x)" if state.xy_lock_max_span else "Lock XY (x)")
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
    """Build the NiceGUI page and store ``ui.echart`` references into *ch*.

    Must be called inside a ``@ui.page``-decorated function.

    Side effects
    ------------
    Assigns ``ch.chart_*`` and ``ch.info_label`` to the created UI elements.
    """
    with ui.column().classes("w-full gap-2 p-2"):
        # ── Header ────────────────────────────────────────────────────────
        with ui.row().classes("items-center gap-4"):
            ui.label("LSL Viewer").classes("text-lg font-bold")
            ui.label(f"mode: {mode}").classes("text-sm bg-blue-100 text-blue-800 px-2 py-0.5 rounded")
            if is_replay:
                ui.label("REPLAY").classes(
                    "text-sm bg-orange-100 text-orange-800 px-2 py-0.5 rounded"
                )

        # ── 1 × 2 time-series grid ────────────────────────────────────────
        with ui.grid(columns=2).classes("w-full gap-2"):
            with ui.row().classes("items-center gap-3 mt-1"):
                # ── Info panel ────────────────────────────────────────────────────
                ch.info_label = ui.label("Waiting for data…").style(
                    "font-family: monospace; font-size: 11px; "
                    "white-space: pre; line-height: 1.35; "
                    "background: #f8f8f8; padding: 6px 8px; border-radius: 4px; "
                    "width: 100%; overflow-x: auto;"
                )

                # ── Control bar ───────────────────────────────────────────────────
                ui.button(
                    "Clear (c)",
                    on_click=lambda: _on_clear(state, ch),
                ).classes("text-xs").props("color=negative outline")

                pause_btn = ui.button("Pause (p)").classes("text-xs").props("color=primary outline")
                pause_btn.on_click(lambda: _on_pause_toggle(state, ch, pause_btn, is_replay=is_replay))

                lock_btn = ui.button("Lock XY (x)").classes("text-xs").props("color=secondary outline")
                lock_btn.on_click(lambda: _on_xy_lock_toggle(state, lock_btn))

                ui.label("  Keyboard: c=clear  p=pause  x=lock-XY").classes("text-xs text-gray-500 ml-2")

            # ── XY panel (full width) ─────────────────────────────────────────
            bind_chart_element(
                ch,
                options_attr="opts_xy",
                chart_attr="chart_xy",
                chart_el=ui.echart(ch.opts_xy).classes(f"w-full {_XY_H}"),
            )

        # ── 3 × 2 time-series grid ────────────────────────────────────────
        with ui.grid(columns=2).classes("w-full gap-2"):
            bind_chart_element(
                ch,
                options_attr="opts_target_raw",
                chart_attr="chart_target_raw",
                chart_el=ui.echart(ch.opts_target_raw).classes(f"w-full {_PANEL_H}"),
            )
            bind_chart_element(
                ch,
                options_attr="opts_reference_raw",
                chart_attr="chart_reference_raw",
                chart_el=ui.echart(ch.opts_reference_raw).classes(f"w-full {_PANEL_H}"),
            )
            bind_chart_element(
                ch,
                options_attr="opts_target_filtered",
                chart_attr="chart_target_filtered",
                chart_el=ui.echart(ch.opts_target_filtered).classes(f"w-full {_PANEL_H}"),
            )
            bind_chart_element(
                ch,
                options_attr="opts_overlay",
                chart_attr="chart_overlay",
                chart_el=ui.echart(ch.opts_overlay).classes(f"w-full {_PANEL_H}"),
            )
            bind_chart_element(
                ch,
                options_attr="opts_target_dt",
                chart_attr="chart_target_dt",
                chart_el=ui.echart(ch.opts_target_dt).classes(f"w-full {_PANEL_H}"),
            )
            bind_chart_element(
                ch,
                options_attr="opts_reference_dt",
                chart_attr="chart_reference_dt",
                chart_el=ui.echart(ch.opts_reference_dt).classes(f"w-full {_PANEL_H}"),
            )

        # ── Keyboard shortcuts (browser key events — no OS focus needed) ──
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
