# @file
# @brief Opt-in live-mode diagnostics for the XY staircase investigation.
##
# The pure helpers (count_target_newer_than_reference_tail, select_new_rows,
# compute_tick_metrics) perform no I/O and are unit-testable in isolation.
# DiagnosticsRecorder is part of the imperative shell: it owns file handles
# and appends per-tick metrics plus deduplicated raw stream samples.
##
# Disabled by default (diagnostics.enabled=false): the recorder is inert and
# creates no files or directories. On any I/O failure it logs an error and
# self-disables so acquisition and rendering are never perturbed.

from __future__ import annotations

import csv
import json
import logging
import math
from datetime import datetime
from pathlib import Path
from typing import IO, Any

import numpy as np
from omegaconf import DictConfig

from lsl_viewer.types import DualWindow, ReferenceWindow, TargetWindow, ViewerState

log = logging.getLogger(__name__)

_TARGET_FIELDS = ["lsl_timestamp_s", "device_clock_us", "raw", "filtered"]
_REFERENCE_FIELDS = ["lsl_timestamp_s", "rs485_clock_s", "raw"]


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def select_new_rows(timestamps_s: np.ndarray, last_logged_ts: float) -> np.ndarray:
    # @brief Boolean mask of finite samples strictly newer than the last logged one.
    # @param timestamps_s Sample timestamps of the current window.
    # @param last_logged_ts Last timestamp already written; nan means none yet.
    # @return Boolean mask selecting rows to append.
    arr = np.asarray(timestamps_s, dtype=np.float64)
    mask = np.isfinite(arr)
    if math.isfinite(last_logged_ts):
        mask &= arr > float(last_logged_ts)
    return mask


def count_target_newer_than_reference_tail(
    target: TargetWindow | None,
    reference: ReferenceWindow | None,
    shift_s: float,
) -> int:
    # @brief Count target samples newer than the shifted reference tail.
    ##
    # These samples are excluded from XY pairing by the `inside` mask in
    # interpolate_reference_to_target(), so this count quantifies how many of
    # the freshest target points the XY plot is currently unable to show.
    # @param target Current target window, or None.
    # @param reference Current reference window, or None.
    # @param shift_s Display-only reference time shift applied during pairing.
    # @return Number of excluded target samples; 0 when either window is empty.
    if target is None or reference is None:
        return 0
    target_t = np.asarray(target.timestamps_s, dtype=np.float64)
    ref_t = np.asarray(reference.timestamps_s, dtype=np.float64)
    finite_ref = ref_t[np.isfinite(ref_t)]
    if target_t.size == 0 or finite_ref.size == 0:
        return 0
    ref_tail = float(finite_ref.max()) + float(shift_s)
    return int(np.sum(np.isfinite(target_t) & (target_t > ref_tail)))


def _latest_finite(values: np.ndarray | None) -> float:
    # @brief Latest finite value of an array, or nan when unavailable.
    # @param values Input array or None.
    # @return Latest finite value, or nan.
    if values is None:
        return float("nan")
    arr = np.asarray(values, dtype=np.float64)
    finite = arr[np.isfinite(arr)]
    return float(finite.max()) if finite.size else float("nan")


def compute_tick_metrics(
    window: DualWindow,
    state: ViewerState,
    *,
    tick_index: int,
    wall_time_s: float,
    monotonic_s: float,
    lsl_local_clock_s: float | None,
    target_new_samples: int,
    reference_new_samples: int,
) -> dict[str, Any]:
    # @brief Build one JSON-serializable metrics record for a render tick.
    # @param window Post-cutoff dual window the charts were rendered from.
    # @param state Viewer state after update_charts (shift/pairing diagnostics).
    # @param tick_index Monotonic tick counter.
    # @param wall_time_s time.time() at recording.
    # @param monotonic_s time.monotonic() at recording.
    # @param lsl_local_clock_s pylsl/mne-lsl local_clock() right after fetch, or None.
    # @param target_new_samples New target samples since previous tick.
    # @param reference_new_samples New reference samples since previous tick.
    # @return Flat dict of metrics; nan values are serialized as None.
    target = window.target
    reference = window.reference
    target_tail = _latest_finite(target.timestamps_s if target is not None else None)
    reference_tail = _latest_finite(reference.timestamps_s if reference is not None else None)
    tail_delta = target_tail - reference_tail

    record: dict[str, Any] = {
        "tick_index": int(tick_index),
        "wall_time_s": float(wall_time_s),
        "monotonic_s": float(monotonic_s),
        "lsl_local_clock_s": None if lsl_local_clock_s is None else float(lsl_local_clock_s),
        "target_tail_s": target_tail,
        "reference_tail_s": reference_tail,
        "tail_delta_s": tail_delta,
        "target_window_n": int(target.timestamps_s.size) if target is not None else 0,
        "reference_window_n": int(reference.timestamps_s.size) if reference is not None else 0,
        "target_new_samples": int(target_new_samples),
        "reference_new_samples": int(reference_new_samples),
        "alignment_mode": str(state.xy_alignment_mode),
        "shift_s": float(state.xy_reference_time_shift_s),
        "shift_clipped": bool(state.xy_reference_shift_clipped),
        "tail_delta_state_s": float(state.xy_reference_tail_delta_s),
        "xy_pair_count": int(state.xy_pair_count),
        "xy_t_min_s": float(state.xy_t_min_s),
        "xy_t_max_s": float(state.xy_t_max_s),
        "target_dropped_newer_than_ref_tail": count_target_newer_than_reference_tail(
            target, reference, state.xy_reference_time_shift_s
        ),
    }
    # JSON has no nan/inf literals; normalize to None for parseable output.
    for key, value in record.items():
        if isinstance(value, float) and not math.isfinite(value):
            record[key] = None
    return record


# ---------------------------------------------------------------------------
# Imperative shell
# ---------------------------------------------------------------------------


class DiagnosticsRecorder:
    # @brief Append-only writer for per-tick metrics and raw stream samples.
    ##
    # One session directory is created lazily on the first write:
    # {output_dir}/{YYYYmmdd_HHMMSS}/ containing metrics.jsonl,
    # target_samples.csv, and reference_samples.csv.

    def __init__(self, cfg: DictConfig) -> None:
        # @brief Create a recorder from the diagnostics config section.
        # @param cfg Full Hydra configuration (uses cfg.diagnostics).
        diag = cfg.diagnostics
        self.enabled = bool(diag.enabled)
        self._output_dir = Path(str(diag.output_dir))
        self._record_metrics = bool(diag.record_metrics)
        self._record_raw_samples = bool(diag.record_raw_samples)
        self._session_dir: Path | None = None
        self._metrics_fh: IO[str] | None = None
        self._target_fh: IO[str] | None = None
        self._reference_fh: IO[str] | None = None
        self._target_writer: Any = None
        self._reference_writer: Any = None
        self._last_target_ts: float = float("nan")
        self._last_reference_ts: float = float("nan")
        self._tick_index: int = 0

    @property
    def session_dir(self) -> Path | None:
        # @brief Session directory once created, or None.
        # @return Path of the active session directory.
        return self._session_dir

    @property
    def tick_index(self) -> int:
        # @brief Number of metric records written so far.
        # @return Current tick counter.
        return self._tick_index

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_tick(self, metrics: dict[str, Any]) -> None:
        # @brief Append one metrics record as a JSONL line.
        # @param metrics JSON-serializable dict from compute_tick_metrics().
        if not self.enabled or not self._record_metrics:
            return
        try:
            self._ensure_open()
            assert self._metrics_fh is not None
            self._metrics_fh.write(json.dumps(metrics, separators=(",", ":")) + "\n")
            self._metrics_fh.flush()
            self._tick_index += 1
        except OSError as exc:
            self._fail(exc)

    def record_window(self, window: DualWindow) -> None:
        # @brief Append samples from the window not yet written (dedupe by timestamp).
        # @param window Post-cutoff dual window from the current tick.
        if not self.enabled or not self._record_raw_samples:
            return
        try:
            self._ensure_open()
            if window.target is not None:
                self._last_target_ts = self._append_rows(
                    self._target_writer,
                    self._target_fh,
                    window.target.timestamps_s,
                    [window.target.device_clock_us, window.target.raw, window.target.filtered],
                    self._last_target_ts,
                )
            if window.reference is not None:
                self._last_reference_ts = self._append_rows(
                    self._reference_writer,
                    self._reference_fh,
                    window.reference.timestamps_s,
                    [window.reference.rs485_clock, window.reference.raw],
                    self._last_reference_ts,
                )
        except OSError as exc:
            self._fail(exc)

    def close(self) -> None:
        # @brief Flush and close all open file handles.
        for fh in (self._metrics_fh, self._target_fh, self._reference_fh):
            if fh is not None:
                try:
                    fh.close()
                except OSError:
                    pass
        self._metrics_fh = None
        self._target_fh = None
        self._reference_fh = None
        self._target_writer = None
        self._reference_writer = None

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _ensure_open(self) -> None:
        # @brief Lazily create the session directory and open output files.
        if self._session_dir is not None:
            return
        session_dir = self._output_dir / datetime.now().strftime("%Y%m%d_%H%M%S")
        session_dir.mkdir(parents=True, exist_ok=True)
        self._session_dir = session_dir
        if self._record_metrics:
            self._metrics_fh = (session_dir / "metrics.jsonl").open("w", encoding="utf-8")
        if self._record_raw_samples:
            self._target_fh = (session_dir / "target_samples.csv").open("w", newline="", encoding="utf-8")
            self._target_writer = csv.writer(self._target_fh)
            self._target_writer.writerow(_TARGET_FIELDS)
            self._reference_fh = (session_dir / "reference_samples.csv").open("w", newline="", encoding="utf-8")
            self._reference_writer = csv.writer(self._reference_fh)
            self._reference_writer.writerow(_REFERENCE_FIELDS)
        log.info("Diagnostics recorder session started: %s", session_dir)

    def _append_rows(
        self,
        writer: Any,
        fh: IO[str] | None,
        timestamps_s: np.ndarray,
        columns: list[np.ndarray],
        last_logged_ts: float,
    ) -> float:
        # @brief Write rows newer than last_logged_ts; return the new high-water mark.
        # @param writer CSV writer for the stream file.
        # @param fh Underlying file handle (flushed after each batch).
        # @param timestamps_s Window timestamps.
        # @param columns Value columns aligned with timestamps_s.
        # @param last_logged_ts Previous high-water timestamp.
        # @return Updated high-water timestamp.
        if writer is None or fh is None:
            return last_logged_ts
        mask = select_new_rows(timestamps_s, last_logged_ts)
        if not np.any(mask):
            return last_logged_ts
        ts = np.asarray(timestamps_s, dtype=np.float64)[mask]
        order = np.argsort(ts)
        ts = ts[order]
        cols = [np.asarray(col, dtype=np.float64)[mask][order] for col in columns]
        for i in range(ts.size):
            writer.writerow([f"{ts[i]:.9f}", *(repr(float(col[i])) for col in cols)])
        fh.flush()
        return float(ts[-1])

    def _fail(self, exc: OSError) -> None:
        # @brief Log the I/O failure once and disable further recording.
        # @param exc Originating OS error.
        log.error("Diagnostics recorder I/O failure; disabling recording: %s", exc)
        self.enabled = False
        self.close()
