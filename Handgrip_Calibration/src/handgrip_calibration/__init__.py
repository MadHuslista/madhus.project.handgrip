"""Calibration workflow package for the dual-device handgrip system.

The package is deliberately separated from the acquisition/visualisation apps.
It owns the calibration session lifecycle, markers, quality checks,
segmentation, fitting, and report generation while consuming the
already-standardised LSL/CSV streams produced by the rest of the Handgrip
stack.
"""

from __future__ import annotations

__version__ = "0.1.0"
