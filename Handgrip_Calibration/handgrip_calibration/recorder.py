"""Live calibration session recorder.

The recorder is intentionally minimal: it subscribes to the already-published LSL
streams, writes canonical CSV files, emits marker events, and records live QA. It
is not a GUI and it does not configure upstream devices. That keeps this module
safe to introduce before modifying the current firmware/app stack.
"""

from __future__ import annotations

import threading
import time
from dataclasses import asdict
from typing import Any

from .config_schema import AppConfig
from .export import append_ndjson
from .lsl_io import CsvStreamRecorder, summarize_stats
from .markers import MarkerLogger
from .protocol import generate_static_trials
from .session import SessionManager, SessionPaths


class CalibrationRecorder:
    """Orchestrate one live calibration recording session."""

    def __init__(self, config: AppConfig, *, session_id: str | None = None) -> None:
        self.config = config
        self.manager = SessionManager(config, session_id=session_id)
        self.stop_event = threading.Event()
        self.recorders: list[CsvStreamRecorder] = []
        self._quality_thread: threading.Thread | None = None

    def _start_recorders(self, paths: SessionPaths) -> None:
        self.recorders = [
            CsvStreamRecorder(
                key="target",
                config=self.config.streams["target"],
                output_csv=paths.target_csv,
                stop_event=self.stop_event,
            ),
            CsvStreamRecorder(
                key="reference",
                config=self.config.streams["reference"],
                output_csv=paths.reference_csv,
                stop_event=self.stop_event,
            ),
        ]
        for recorder in self.recorders:
            recorder.start()

    def _start_quality_logging(self, paths: SessionPaths) -> None:
        def loop() -> None:
            while not self.stop_event.is_set():
                append_ndjson(paths.quality, [{"host_time_unix": time.time(), "streams": summarize_stats(self.recorders)}])
                time.sleep(self.config.quality.quality_emit_period_s)

        self._quality_thread = threading.Thread(target=loop, name="CalibrationQualityLogger", daemon=True)
        self._quality_thread.start()

    def run_static_staircase(self) -> SessionPaths:  # pragma: no cover - interactive/live workflow
        """Run the configured static-staircase protocol.

        This method is intended for a human operator at the bench. It uses fixed
        timing for stable windows, while the operator physically applies and
        releases force levels.
        """

        paths = self.manager.create()
        markers = MarkerLogger(paths.events, self.config.markers, session_id=self.manager.session_id)
        self._start_recorders(paths)
        self._start_quality_logging(paths)
        protocol = self.config.protocol
        trials = generate_static_trials(protocol)

        markers.emit("session_start", payload={"protocol": protocol.name})
        try:
            if protocol.warmup_s > 0:
                print(f"Warmup: wait {protocol.warmup_s:.1f}s")
                time.sleep(protocol.warmup_s)

            input("Remove load for baseline, then press ENTER...") if protocol.prompt_operator else None
            markers.emit("baseline_start", phase="baseline", target_force_N=0.0)
            time.sleep(protocol.baseline_duration_s)
            markers.emit("baseline_end", phase="baseline", target_force_N=0.0)

            if protocol.preload_enabled:
                for cycle in range(1, protocol.preload_cycles + 1):
                    input(f"Preload cycle {cycle}/{protocol.preload_cycles}: apply up to {protocol.preload_max_force_N:g} N, then press ENTER...") if protocol.prompt_operator else None
                    markers.emit("preload", phase="preload", payload={"cycle": cycle, "max_force_N": protocol.preload_max_force_N})

            for trial in trials:
                if protocol.prompt_operator:
                    input(f"Apply {trial.target_force_N:g} N for {trial.trial_id}, then press ENTER to start hold...")
                markers.emit(
                    "hold_start",
                    trial_id=trial.trial_id,
                    target_force_N=trial.target_force_N,
                    phase="static_hold",
                    payload=asdict(trial),
                )
                # Stable window begins at the tail of the hold. This avoids using
                # the initial settling transient for the calibration fit.
                initial_s = max(0.0, protocol.hold_duration_s - protocol.stable_window_s)
                time.sleep(initial_s)
                markers.emit("stable_window_start", trial_id=trial.trial_id, target_force_N=trial.target_force_N, phase="static_hold")
                time.sleep(protocol.stable_window_s)
                markers.emit("hold_end", trial_id=trial.trial_id, target_force_N=trial.target_force_N, phase="static_hold")

                accepted = protocol.auto_accept_holds
                reason = None
                if protocol.prompt_operator and not protocol.auto_accept_holds:
                    response = input("Accept this hold? [Y/n/reason] ").strip()
                    accepted = response == "" or response.lower().startswith("y")
                    if not accepted:
                        reason = response or "operator_rejected"
                markers.emit("trial_accept" if accepted else "trial_reject", trial_id=trial.trial_id, target_force_N=trial.target_force_N, reason=reason)

            if protocol.dynamic_slow_ramps:
                input(f"Run {protocol.dynamic_slow_ramps} slow ramp validation trial(s), then press ENTER...") if protocol.prompt_operator else None
                markers.emit("dynamic_validation", phase="slow_ramp", payload={"count": protocol.dynamic_slow_ramps})
            if protocol.dynamic_fast_squeezes:
                input(f"Run {protocol.dynamic_fast_squeezes} fast squeeze validation trial(s), then press ENTER...") if protocol.prompt_operator else None
                markers.emit("dynamic_validation", phase="fast_squeeze", payload={"count": protocol.dynamic_fast_squeezes})

            markers.emit("session_end", payload={"recording_stats": summarize_stats(self.recorders)})
        finally:
            self.stop_event.set()
            for recorder in self.recorders:
                recorder.join(timeout=2.0)
            if self._quality_thread is not None:
                self._quality_thread.join(timeout=2.0)
        return paths
