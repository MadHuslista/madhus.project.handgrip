"""Calibration workflow package for the dual-device handgrip system.

The package is deliberately separated from the acquisition/visualization apps. It
owns the calibration session lifecycle, markers, quality checks, segmentation,
fitting, and report generation while consuming the already-standardized LSL/CSV
streams produced by the rest of the Handgrip stack.
"""

from __future__ import annotations

__version__ = "0.1.0"
