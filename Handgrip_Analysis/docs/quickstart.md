# Handgrip Analysis Quickstart

## Summary

- Use this quickstart to run offline `Handgrip_Analysis` on saved data.
- Run analysis only after acquisition/calibration data or curated CSV inputs exist.
- Start with `--help`, then run either all stages from a manifest or one stage on a specific input.
- Treat command examples as canonical shapes; if the active CLI differs, update this doc and `docs/workflows/handgrip-analysis.md` together.

## Prerequisites

- Python dependencies installed with `uv`.
- Input CSV/session data exists and can be traced to a source capture.
- Channel mapping is known: timestamp column, signal column, condition labels, and sampling assumptions.
- Config files exist under `Handgrip_Analysis/conf/`.

Recommended first check:

```bash
cd Handgrip_Analysis
uv run ha-run-all --help
uv run ha-stage --help
```

If the current package exposes stage-specific commands such as `ha-stage1` or `ha-stage6`, inspect them too:

```bash
uv run ha-stage1 --help
uv run ha-stage6 --help
```

## Run all stages

Use a manifest when running a complete analysis pass:

```bash
cd Handgrip_Analysis
uv run ha-run-all \
  manifest=data/manifests/capture_manifest.csv \
  base_outdir=data/analysis_results/batch_run
```

Expected result:

- manifest is parsed,
- all configured stages run or explicitly skip with documented reason,
- output directory is created,
- stage reports and metrics are written,
- errors identify missing files/columns clearly.

## Run an individual stage

Generic stage command shape:

```bash
cd Handgrip_Analysis
uv run ha-stage stage=stage6 \
  manifest=data/manifests/stage6_filter_review_manifest.csv \
  outdir=data/analysis_results/stage6 \
  filter_config=conf/filters/candidates.yaml
```

Stage-specific command shape, when supported:

```bash
uv run ha-stage6 \
  input=data/calibration_signals/20260402_stage4_ramp_hold_trial01.csv \
  outdir=data/analysis_results/stage6_ramp_hold \
  filter_config=conf/filters/candidates.yaml
```

If the command fails because an entry point does not exist, check `pyproject.toml` and update this doc to the active CLI shape.

## Expected result

A successful run produces:

| Output | Purpose |
| --- | --- |
| stage report | Human-readable analysis result. |
| metrics JSON/CSV | Machine-readable result data. |
| figures | Visual diagnostics. |
| run config snapshot | Reproducibility and audit trail, when enabled. |
| Stage 6 recommendation | Candidate ranking and deployment guidance, when Stage 6 runs. |

## Where outputs/logs appear

Typical locations:

```text
Handgrip_Analysis/data/analysis_results/<run_or_stage_id>/
Handgrip_Analysis/outputs/<run_or_stage_id>/
```

Exact paths are config-owned. See [`configuration.md`](configuration.md) and [`reports-and-outputs.md`](reports-and-outputs.md).

## Stop conditions

Stop and fix inputs/configs if:

- manifest points to missing files,
- required columns are absent,
- sampling rate is unknown for DSP stages,
- stage output is empty,
- Stage 6 lacks candidate comparison metrics,
- selected filter recommendation cannot be traced to stage metrics,
- generated output overwrites a prior run unintentionally.

## Troubleshooting links

- [`configuration.md`](configuration.md)
- [`stages.md`](stages.md)
- [`reports-and-outputs.md`](reports-and-outputs.md)
- [`../../docs/workflows/handgrip-analysis.md`](../../docs/workflows/handgrip-analysis.md)
- [`../../docs/architecture/data-and-output-lifecycle.md`](../../docs/architecture/data-and-output-lifecycle.md)
