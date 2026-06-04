#!/usr/bin/env python3
# @package scripts.run_manifest_analysis
# @brief Run Phase 1 manifest-driven multi-trial analysis.

"""
Run Phase 1 manifest-driven multi-trial analysis.

Example:
-------
python scripts/run_manifest_analysis.py \
  --manifest data/calibration_manifest.csv \
  --stage stage1 \
  --outdir data/analysis_results/stage1

"""

from __future__ import annotations

from handgrip_analysis._cli.manifest import main

# @brief CLI entrypoint for manifest-driven analysis.
# @return None.
if __name__ == "__main__":
    main()
