"""Live calibration session recorder.

The recorder subscribes to the already-published LSL streams, writes canonical
CSV files, emits marker events, and records live QA. It intentionally does not
configure the upstream firmware, LSL bridge, RS485 GUI, or acquisition board.

This version implements the full calibration-campaign protocol layer:
reference verification, static reversible staircase, low-force refinement,
creep/zero-return characterization, dynamic validation, and independent holdout
verification. Static-style protocols continue to emit the same ``hold_*`` and
``trial_accept`` markers used by the existing offline segmenter/fitter.
"""

from __future__ import annotations

import logging
import threading
import time
import warnings
from dataclasses import asdict
from typing import Any

from .config_schema import AppConfig
from .export import append_ndjson
from .lsl_io import CsvStreamRecorder, summarize_stats
from .logging_setup import configure_logging
from .markers import MarkerLogger
from .protocol import Trial, generate_static_trials
from .session import SessionManager, SessionPaths

log = logging.getLogger(__name__)


class CalibrationRecorder:
    """Orchestrate one live calibration recording session."""

    def __init__(self, config: AppConfig, *, session_id: str | None = None, yes: bool = False) -> None:
        self.config = config
        self.yes = yes
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

    def _operator_continue(self, message: str) -> None:  # pragma: no cover - interactive/live workflow
        log.info("Operator prompt: %s", message)
        if self.config.protocol.prompt_operator and not self.yes:
            input(message)

    def _timed_wait(self, duration_s: float, *, message: str | None = None) -> None:  # pragma: no cover - interactive/live workflow
        if message:
            log.info("%s", message)
        if duration_s > 0:
            time.sleep(duration_s)

    def _run_baseline(self, markers: MarkerLogger) -> None:  # pragma: no cover - interactive/live workflow
        protocol = self.config.protocol
        self._operator_continue("Remove load for baseline / zero observation, then press ENTER...")
        markers.emit("baseline_start", phase="baseline", target_force_N=0.0)
        self._timed_wait(protocol.baseline_duration_s, message=f"Baseline: recording {protocol.baseline_duration_s:.1f}s")
        markers.emit("baseline_end", phase="baseline", target_force_N=0.0)

    def _run_preload(self, markers: MarkerLogger) -> None:  # pragma: no cover - interactive/live workflow
        protocol = self.config.protocol
        if not protocol.preload_enabled or protocol.preload_cycles <= 0:
            return
        for cycle in range(1, protocol.preload_cycles + 1):
            self._operator_continue(
                f"Preload cycle {cycle}/{protocol.preload_cycles}: apply up to "
                f"{protocol.preload_max_force_N:g} N, then press ENTER to mark preload_start..."
            )
            markers.emit(
                "preload_start",
                phase="preload",
                target_force_N=protocol.preload_max_force_N,
                payload={"cycle": cycle, "max_force_N": protocol.preload_max_force_N},
            )
            self._timed_wait(protocol.preload_hold_duration_s, message="Preload hold running...")
            markers.emit(
                "preload_end",
                phase="preload",
                target_force_N=protocol.preload_max_force_N,
                payload={"cycle": cycle, "max_force_N": protocol.preload_max_force_N},
            )
            if protocol.preload_recovery_duration_s > 0:
                self._operator_continue("Release preload to zero, then press ENTER to start recovery wait...")
                self._timed_wait(protocol.preload_recovery_duration_s, message="Preload recovery wait running...")

    def _run_static_trials(self, markers: MarkerLogger) -> None:  # pragma: no cover - interactive/live workflow
        protocol = self.config.protocol
        trials = generate_static_trials(protocol)
        by_repeat: dict[int, list[Trial]] = {}
        for trial in trials:
            by_repeat.setdefault(trial.repeat_index, []).append(trial)

        for repeat_index in sorted(by_repeat):
            markers.emit(
                "series_start",
                phase="static_hold_series",
                payload={"repeat_index": repeat_index, "n_trials": len(by_repeat[repeat_index])},
            )
            for trial in by_repeat[repeat_index]:
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
                self._timed_wait(initial_s)
                markers.emit("stable_window_start", trial_id=trial.trial_id, target_force_N=trial.target_force_N, phase="static_hold")
                self._timed_wait(protocol.stable_window_s)
                markers.emit("hold_end", trial_id=trial.trial_id, target_force_N=trial.target_force_N, phase="static_hold")

                accepted = protocol.auto_accept_holds
                reason = None
                if protocol.prompt_operator and not protocol.auto_accept_holds:
                    response = input("Accept this hold? [Y/n/reason] ").strip()
                    accepted = response == "" or response.lower().startswith("y")
                    if not accepted:
                        reason = response or "operator_rejected"
                markers.emit("trial_accept" if accepted else "trial_reject", trial_id=trial.trial_id, target_force_N=trial.target_force_N, reason=reason)
            markers.emit(
                "series_end",
                phase="static_hold_series",
                payload={"repeat_index": repeat_index, "n_trials": len(by_repeat[repeat_index])},
            )

    def _run_creep_zero_return(self, markers: MarkerLogger) -> None:  # pragma: no cover - interactive/live workflow
        creep_cfg = self.config.creep
        force_levels = creep_cfg.force_levels_N
        durations = list(creep_cfg.durations_s)
        read_times = creep_cfg.read_times_s
        if len(durations) < len(force_levels):
            durations = durations + [float(durations[-1])] * (len(force_levels) - len(durations))

        for idx, force in enumerate(float(x) for x in force_levels):
            duration_s = float(durations[idx])
            is_zero = abs(force) <= 1e-9
            phase = "zero_return" if is_zero else "creep"
            start_event = "zero_return_start" if is_zero else "creep_start"
            end_event = "zero_return_end" if is_zero else "creep_end"
            self._operator_continue(f"Set force to {force:g} N for {phase} stage {idx + 1}, then press ENTER...")
            markers.emit(start_event, phase=phase, target_force_N=force, payload={"stage_index": idx + 1, "duration_s": duration_s})
            elapsed = 0.0
            for read_t in read_times:
                if read_t <= elapsed or read_t > duration_s:
                    continue
                self._timed_wait(read_t - elapsed)
                elapsed = read_t
                if not is_zero:
                    event_name = "creep_read_30s" if abs(read_t - 30.0) < 1e-6 else "creep_read_300s" if abs(read_t - 300.0) < 1e-6 else "creep_read"
                    markers.emit(event_name, phase=phase, target_force_N=force, payload={"stage_index": idx + 1, "elapsed_s": read_t})
                else:
                    markers.emit("zero_return_read", phase=phase, target_force_N=force, payload={"stage_index": idx + 1, "elapsed_s": read_t})
            if duration_s > elapsed:
                self._timed_wait(duration_s - elapsed)
            markers.emit(end_event, phase=phase, target_force_N=force, payload={"stage_index": idx + 1, "duration_s": duration_s})

    def _run_dynamic_validation(self, markers: MarkerLogger) -> None:  # pragma: no cover - interactive/live workflow
        dyn_cfg = self.config.dynamic

        for ramp in dyn_cfg.ramps:
            if ramp.count <= 0:
                continue
            ramp_dict = {"label": ramp.label, "count": ramp.count, "peak_force_N": ramp.peak_force_N, "speed_N_per_s": ramp.speed_N_per_s}
            for idx in range(1, ramp.count + 1):
                self._operator_continue(
                    f"Prepare ramp {ramp.label} {idx}/{ramp.count}: 0 -> {ramp.peak_force_N:g} N -> 0, "
                    f"about {ramp.speed_N_per_s:g} N/s. Press ENTER at ramp start..."
                )
                markers.emit("ramp_start", phase="dynamic_ramp", payload={**ramp_dict, "index": idx})
                self._operator_continue("Press ENTER when this ramp is complete...")
                markers.emit("ramp_end", phase="dynamic_ramp", payload={**ramp_dict, "index": idx})

        for squeeze in dyn_cfg.squeezes:
            if squeeze.count <= 0:
                continue
            squeeze_dict = {"label": squeeze.label, "count": squeeze.count, "peak_force_N": squeeze.peak_force_N, "rest_s": squeeze.rest_s}
            for idx in range(1, squeeze.count + 1):
                self._operator_continue(
                    f"Prepare squeeze {squeeze.label} {idx}/{squeeze.count}; press ENTER at squeeze start..."
                )
                markers.emit("squeeze_start", phase="dynamic_squeeze", payload={**squeeze_dict, "index": idx})
                self._operator_continue("Press ENTER when this squeeze/release is complete...")
                markers.emit("squeeze_end", phase="dynamic_squeeze", payload={**squeeze_dict, "index": idx})
                if squeeze.rest_s > 0 and idx < squeeze.count:
                    self._timed_wait(squeeze.rest_s, message=f"Resting {squeeze.rest_s:g}s before next squeeze...")

    def run_protocol(self) -> SessionPaths:  # pragma: no cover - interactive/live workflow
        """Run the configured live recording protocol."""

        protocol = self.config.protocol
        paths = self.manager.create(extra_manifest={"protocol_type": protocol.protocol_type})
        configure_logging(level="DEBUG", log_file=paths.session_log)
        log.info(
            "Session started: %s (protocol=%s)",
            self.manager.session_id,
            protocol.protocol_type,
        )
        markers = MarkerLogger(paths.events, self.config.markers, session_id=self.manager.session_id)
        self._start_recorders(paths)
        self._start_quality_logging(paths)

        start_event_by_type = {
            "reference_verification": "reference_verification_start",
            "holdout_verification": "holdout_start",
        }
        end_event_by_type = {
            "reference_verification": "reference_verification_end",
            "holdout_verification": "holdout_end",
        }
        try:
            markers.emit("session_start", payload={"protocol": protocol.name, "protocol_type": protocol.protocol_type})
            if protocol.protocol_type in start_event_by_type:
                markers.emit(start_event_by_type[protocol.protocol_type], phase=protocol.protocol_type, payload={"protocol": protocol.name})

            if protocol.warmup_s > 0:
                log.info("Warmup: waiting %.1f s", protocol.warmup_s)
                time.sleep(protocol.warmup_s)

            if protocol.protocol_type in {"reference_verification", "static_staircase", "low_force_refinement", "holdout_verification"}:
                self._run_baseline(markers)
                self._run_preload(markers)
                self._run_static_trials(markers)
            elif protocol.protocol_type == "creep_zero_return":
                self._run_baseline(markers)
                self._run_creep_zero_return(markers)
            elif protocol.protocol_type == "dynamic_validation":
                self._run_baseline(markers)
                self._run_dynamic_validation(markers)
            else:
                raise ValueError(f"Unsupported protocol type: {protocol.protocol_type}")

            if protocol.protocol_type in end_event_by_type:
                markers.emit(end_event_by_type[protocol.protocol_type], phase=protocol.protocol_type, payload={"protocol": protocol.name})
            markers.emit("session_end", payload={"recording_stats": summarize_stats(self.recorders)})
        finally:
            self.stop_event.set()
            for recorder in self.recorders:
                recorder.join(timeout=2.0)
            if self._quality_thread is not None:
                self._quality_thread.join(timeout=2.0)
        return paths

    def run_static_staircase(self) -> SessionPaths:  # pragma: no cover - compatibility wrapper
        """Deprecated. Use ``run_protocol()`` instead. Will be removed in v0.3.0."""
        warnings.warn(
            "run_static_staircase() is deprecated. Use run_protocol() instead. "
            "Will be removed in v0.3.0.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.run_protocol()
