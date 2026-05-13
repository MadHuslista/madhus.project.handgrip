#!/usr/bin/env python3
"""Run Phase 1 manifest-driven multi-trial analysis.

Example
-------
python scripts/run_manifest_analysis.py \
  --manifest data/calibration_manifest.csv \
  --stage stage1 \
  --outdir data/analysis_results/stage1
"""
from __future__ import annotations

from handgrip_analysis._cli.manifest import main


if __name__ == "__main__":
    main()
