#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import pandas as pd


STAGE_TO_SCRIPT = {
    "stage1": "stage1_startup_warmup.py",
    "stage2": "stage2_static_noise.py",
    "stage3": "stage3_loaded_drift.py",
    "stage4": "stage4_grip_dynamics.py",
    "stage5": None,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dispatch manifest rows to stage scripts")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--base-outdir", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = pd.read_csv(args.manifest)
    project_root = Path(__file__).resolve().parent.parent
    scripts_dir = project_root / "scripts"
    base_outdir = Path(args.base_outdir)
    base_outdir.mkdir(parents=True, exist_ok=True)

    for _, row in manifest.iterrows():
        stage = str(row["stage"])
        label = str(row["label"])
        path = str(row["path"])
        channel = str(row.get("channel", "raw"))
        outdir = base_outdir / label
        if stage == "stage5":
            continue
        script_name = STAGE_TO_SCRIPT.get(stage)
        if not script_name:
            continue
        cmd = [
            "python",
            str(scripts_dir / script_name),
            "--input",
            path,
            "--outdir",
            str(outdir),
        ]
        if stage != "stage2":
            cmd.extend(["--channel", channel])
        subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
