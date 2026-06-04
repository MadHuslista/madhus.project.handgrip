#!/usr/bin/env python3
# @package scripts.run_all
# @brief Batch dispatcher routing manifest rows to stage scripts.

"""
Batch dispatcher — routes manifest rows to the appropriate stage script.

Manifest CSV columns: stage, label, path [, channel]

Supported stage values:
    stage1, stage2, stage3, stage4, stage5, stage6_design, stage6_review
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

import hydra
import pandas as pd
from handgrip_analysis._logging import setup_logging
from omegaconf import DictConfig

log = logging.getLogger(__name__)

STAGE_TO_SCRIPT: dict[str, str] = {
    "stage1": "stage1_startup_warmup.py",
    "stage2": "stage2_static_noise.py",
    "stage3": "stage3_loaded_drift.py",
    "stage4": "stage4_grip_dynamics.py",
    "stage5": "stage5_interference_compare.py",
    "stage6_design": "stage6_filter_design.py",
    "stage6_review": "stage6_filter_family_review.py",
}


# @brief Run all manifest rows by dispatching each stage to its script.
# @param cfg Hydra configuration object.
# @return None.
@hydra.main(config_path="../conf", config_name="config", version_base="1.3")
def main(cfg: DictConfig) -> None:
    setup_logging(level=cfg.logging.level, log_file=cfg.logging.file)
    log.info("run_all: reading manifest %s", cfg.manifest)

    manifest = pd.read_csv(cfg.manifest)
    scripts_dir = Path(__file__).resolve().parent
    base_outdir = Path(cfg.base_outdir)
    base_outdir.mkdir(parents=True, exist_ok=True)

    skipped = 0
    dispatched = 0

    for _, row in manifest.iterrows():
        stage = str(row["stage"])
        label = str(row["label"])
        path = str(row["path"])
        channel = str(row.get("channel", "raw"))
        outdir = base_outdir / label

        script_name = STAGE_TO_SCRIPT.get(stage)
        if not script_name:
            log.warning("run_all: unknown stage %r for label %r — skipping", stage, label)
            skipped += 1
            continue

        script_path = scripts_dir / script_name
        cmd = [
            sys.executable,
            str(script_path),
            f"input={path}",
            f"outdir={outdir}",
            f"io.time_source={cfg.io.time_source}",
            f"logging.level={cfg.logging.level}",
            f"analysis={stage}",
        ]
        if stage not in ("stage2",):
            cmd.append(f"analysis.channel={channel}")

        log.info("run_all: dispatching %s → %s (label=%r)", stage, script_name, label)
        result = subprocess.run(cmd, check=False)
        if result.returncode != 0:
            log.error(
                "run_all: script %s failed for label %r (exit code %d)",
                script_name,
                label,
                result.returncode,
            )
        else:
            dispatched += 1

    log.info(
        "run_all: complete — %d dispatched, %d skipped",
        dispatched,
        skipped,
    )


if __name__ == "__main__":
    main()
