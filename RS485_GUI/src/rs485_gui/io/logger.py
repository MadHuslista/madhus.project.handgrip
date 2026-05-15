"""File logger for acquisition data.

Writes four files per session:
  - ``raw_signal.ndjson``         — raw transport bytes / register hex
  - ``interpreted_signal.ndjson`` — decoded engineering values
  - ``gui_signal.csv``            — flat CSV optimised for spreadsheet import
  - ``event.log``                 — operational event messages

All file I/O is serialised through a single lock; the worker thread calls
``write_frames()`` at full acquisition rate while the UI thread may
call ``write_event()`` at any time.

Dependency chain: models, core/signals  (no UI)
"""
from __future__ import annotations

import csv
import json
import logging
import threading
import time
from pathlib import Path
from typing import TextIO

from omegaconf import DictConfig

from rs485_gui.core.signals import extract_plot_value, get_plot_signal_key
from rs485_gui.models import MeasurementFrame

LOGGER = logging.getLogger(__name__)


## @brief Represents the SignalFileLogger component.
class SignalFileLogger:
    """Thread-safe writer for the four acquisition log files."""

    ## @brief Init.
    #
    #  @param self Parameter description.
    #  @param cfg Parameter description.
    def __init__(self, cfg: DictConfig) -> None:
        self.cfg = cfg
        self.enabled = bool(cfg.logger.enabled)
        self.directory = Path(str(cfg.logger.directory)).expanduser()
        self.write_mode = str(cfg.logger.write_mode).lower()
        if self.write_mode not in {'append', 'overwrite'}:
            raise ValueError(
                f'logger.write_mode must be "append" or "overwrite", got {self.write_mode!r}'
            )

        self.raw_path = self.directory / str(cfg.logger.raw_signal_filename)
        self.interpreted_path = self.directory / str(cfg.logger.interpreted_signal_filename)
        self.gui_path = self.directory / str(cfg.logger.gui_signal_filename)
        self.event_path = self.directory / str(cfg.logger.event_log_filename)

        self._raw_fp: TextIO | None = None
        self._interpreted_fp: TextIO | None = None
        self._gui_fp: TextIO | None = None
        self._event_fp: TextIO | None = None
        self._gui_writer: csv.writer | None = None
        self._lock = threading.Lock()
        self._write_batches_since_flush: int = 0
        self._last_flush_monotonic: float = time.monotonic()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def open(self) -> None:
        """Open all log files.  Safe to call on reconnect; previous files are flushed first."""
        if not self.enabled:
            return

        self.directory.mkdir(parents=True, exist_ok=True)
        file_mode = 'a' if self.write_mode == 'append' else 'w'

        self._raw_fp = self.raw_path.open(file_mode, encoding='utf-8', newline='')
        self._interpreted_fp = self.interpreted_path.open(file_mode, encoding='utf-8', newline='')

        gui_file_preexisting = self.gui_path.exists() and self.gui_path.stat().st_size > 0
        self._gui_fp = self.gui_path.open(file_mode, encoding='utf-8', newline='')
        self._event_fp = self.event_path.open(file_mode, encoding='utf-8', newline='')
        self._gui_writer = csv.writer(self._gui_fp)
        self._write_batches_since_flush = 0
        self._last_flush_monotonic = time.monotonic()

        if self.write_mode == 'overwrite' or not gui_file_preexisting:
            self._gui_writer.writerow([
                'host_ts_epoch_s', 'host_ts_iso', 'session_id', 'mode',
                'reference_force_N', 'reference_clock_s', 'reference_status',
                'plot_signal_key', 'plot_value',
            ])
            self._flush_unlocked()

    ## @brief Close.
    #
    #  @param self Parameter description.
    def close(self) -> None:
        """Flush and close all open log files."""
        with self._lock:
            self._flush_unlocked()
            for fp in (self._raw_fp, self._interpreted_fp, self._gui_fp, self._event_fp):
                if fp is not None and not fp.closed:
                    fp.flush()
                    fp.close()
            self._raw_fp = None
            self._interpreted_fp = None
            self._gui_fp = None
            self._event_fp = None
            self._gui_writer = None

    # ------------------------------------------------------------------
    # Writing
    # ------------------------------------------------------------------

    def write_frames(self, frames: list[MeasurementFrame]) -> None:
        """Write a batch of frames to the NDJSON and CSV logs."""
        if not self.enabled or not frames:
            return
        with self._lock:
            if self._raw_fp is None or self._interpreted_fp is None or self._gui_writer is None:
                raise RuntimeError('SignalFileLogger.write_frames called before open()')

            plot_signal_key = get_plot_signal_key(self.cfg)
            for frame in frames:
                raw_record = {
                    'host_ts_epoch_s': frame.host_ts,
                    'host_ts_iso': frame.host_ts_iso,
                    'session_id': frame.session_id,
                    'mode': frame.mode,
                    'raw_transport': frame.raw_transport,
                    'board_profile': frame.board_profile,
                }
                interpreted_record = {
                    'host_ts_epoch_s': frame.host_ts,
                    'host_ts_iso': frame.host_ts_iso,
                    'session_id': frame.session_id,
                    'mode': frame.mode,
                    'interpreted': frame.interpreted,
                    'board_profile': frame.board_profile,
                }
                self._raw_fp.write(json.dumps(raw_record, ensure_ascii=False) + '\n')
                self._interpreted_fp.write(
                    json.dumps(interpreted_record, ensure_ascii=False) + '\n'
                )
                plot_value = extract_plot_value(frame, self.cfg)
                self._gui_writer.writerow([
                    frame.host_ts,
                    frame.host_ts_iso,
                    frame.session_id,
                    frame.mode,
                    frame.interpreted.get('reference_force_N'),
                    frame.interpreted.get('reference_clock_s'),
                    frame.interpreted.get('reference_status'),
                    plot_signal_key,
                    plot_value,
                ])

            self._write_batches_since_flush += 1
            flush_every_n = max(1, int(self.cfg.logger.flush_every_n_batches))
            flush_interval_s = float(self.cfg.logger.flush_interval_s)
            should_flush = self._write_batches_since_flush >= flush_every_n
            if flush_interval_s > 0 and (
                time.monotonic() - self._last_flush_monotonic
            ) >= flush_interval_s:
                should_flush = True
            if should_flush:
                self._flush_unlocked()

    ## @brief Write frame.
    #
    #  @param self Parameter description.
    #  @param frame Parameter description.
    def write_frame(self, frame: MeasurementFrame) -> None:
        """Write a single frame (convenience wrapper)."""
        self.write_frames([frame])

    ## @brief Write event.
    #
    #  @param self Parameter description.
    #  @param line Parameter description.
    def write_event(self, line: str) -> None:
        """Append one event line to the event log."""
        if not self.enabled:
            return
        with self._lock:
            if self._event_fp is None:
                return
            self._event_fp.write(line + '\n')
            self._event_fp.flush()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _flush_unlocked(self) -> None:
        """Flush all open file handles.  Must be called with ``self._lock`` held."""
        for fp in (self._raw_fp, self._interpreted_fp, self._gui_fp, self._event_fp):
            if fp is not None and not fp.closed:
                fp.flush()
        self._write_batches_since_flush = 0
        self._last_flush_monotonic = time.monotonic()
