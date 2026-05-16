# Handgrip Analysis Workflow

**Status:** Canonical operator workflow  
**Audience:** Maintainers, analysts, and principal investigator  
**Scope:** Offline signal analysis, stage execution, manifests, outputs, Stage 6 filter design interpretation  
**Related docs:** `Handgrip_Analysis/README.md`, `Handgrip_Analysis/docs/stages.md`, `Handgrip_Analysis/docs/filter-design.md`

## Summary

`Handgrip_Analysis` is the offline analysis framework for characterizing signal quality and evaluating DSP/filter alternatives. It should consume saved calibration/session/CSV data, not live streams, unless a future stage explicitly documents live behavior.

## 1 — Required input data organization

Inputs should be organized so every run can be traced back to a source session or source file.

Recommended structure:

```text
Handgrip_Analysis/
├── data/
│   ├── manifests/
│   ├── raw/ or imported/
│   └── analysis_results/
└── conf/
```

Each input file should have clear provenance:

- source session ID,
- date/time,
- target/reference identity,
- protocol name,
- relevant config snapshot or link.

## 2 — Manifest requirements

A manifest should tell the analysis stage what files to load and how to label them.

Minimum expected manifest concepts:

| Field class            | Purpose                                             |
| ---------------------- | --------------------------------------------------- |
| source path            | CSV/session file to analyze.                        |
| session/protocol label | Human-readable provenance.                          |
| signal/channel mapping | Which columns represent time/value/force/raw count. |
| condition label        | Rest/load/dynamic/filter candidate/etc.             |
| output grouping        | How reports aggregate results.                      |

If a stage fails because a column is missing, fix the manifest or input export instead of hard-coding path-specific behavior.

## 3 — Stage list

| Stage   | Purpose                           | Typical output                        |
| ------- | --------------------------------- | ------------------------------------- |
| Stage 1 | Startup/warm-up behavior          | stabilization metrics and plots.      |
| Stage 2 | Static rest noise                 | noise metrics, PSD/bandpower.         |
| Stage 3 | Loaded drift/creep                | drift slopes and hold stability.      |
| Stage 4 | Real handgrip dynamics            | rise/peak/release dynamics.           |
| Stage 5 | Interference/condition comparison | condition comparison report.          |
| Stage 6 | Filter candidate benchmark/design | rankings, recommendation YAML/report. |

## 4 — Commands to run all vs single stages

Exact CLI names may vary by installed package entry points. Use the component README and `--help` to confirm.

From `Handgrip_Analysis/`:

```bash
cd Handgrip_Analysis
uv run ha-stage --help
```

Single-stage example:

```bash
uv run ha-stage stage=stage6 \
  manifest=data/manifests/stage6_filter_review_manifest.csv \
  outdir=data/analysis_results/stage6 \
  filter_config=conf/filters/candidates.yaml
```

If the current CLI uses a different command shape, update this workflow and `Handgrip_Analysis/docs/quickstart.md` together.

## 5 — Output locations

Typical output locations:

| Output                 | Typical location                                                     |
| ---------------------- | -------------------------------------------------------------------- |
| stage reports          | `Handgrip_Analysis/data/analysis_results/<stage>/`                   |
| figures                | stage output folder or configured plot path                          |
| metrics                | JSON/CSV in stage output folder                                      |
| Stage 6 recommendation | `lsl_bridge_processing_recommendation.yaml` or configured equivalent |
| curated examples       | `docs/examples/analysis-output/`                                     |

Generated analysis output is not canonical documentation unless curated under `docs/examples/`.

## 6 — Interpretation of Stage 6 filter design outputs

Stage 6 should answer:

1. Which filter candidates were evaluated?
2. Which metrics were used?
3. Which candidate best balances noise reduction, lag, signal distortion, and implementation complexity?
4. Whether the recommendation should be applied in firmware, `LSL_Bridge`, viewer display only, or analysis only.

Interpretation rules:

- Prefer filters that improve signal quality without hiding important dynamics.
- Do not choose a filter solely because it looks smoother.
- Treat latency/phase behavior as calibration-relevant.
- Preserve raw data whenever possible.

## 7 — What to do with selected filter recommendations

| Recommendation target   | Action                                                                                          |
| ----------------------- | ----------------------------------------------------------------------------------------------- |
| `LSL_Bridge` processing | Copy/update relevant processing config and validate live stream behavior.                       |
| Viewer display only     | Change viewer config, not acquisition data path.                                                |
| Firmware                | Update firmware only if the filter must exist on-device; validate serial and calibration again. |
| Analysis only           | Keep recommendation in analysis config/report; do not alter live acquisition.                   |

After applying a filter recommendation, rerun a validation subset and compare:

- raw vs filtered signal,
- lag/phase behavior,
- calibration residuals,
- dynamic trial behavior.

## Stop conditions

Stop and troubleshoot if:

- manifest points to missing files,
- required columns are absent,
- stage output is empty,
- Stage 6 report lacks candidate comparison,
- recommendation cannot be traced back to metrics,
- selected filter changes calibration interpretation without a validation run.

## Troubleshooting links

- `Handgrip_Analysis/README.md`
- `Handgrip_Analysis/docs/configuration.md`
- `Handgrip_Analysis/docs/filter-design.md`
- `docs/architecture/data-and-output-lifecycle.md`
