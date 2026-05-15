# Stage 6 Context Resolution Fix

## Issue

When `ha-stage stage=stage6` was run with `data/manifests/stage6_filter_review_manifest.csv`, the generated `stage6_review_design_report.md` marked Stage 1–5 insights as unavailable. The Stage 6 manifest is intentionally Stage 6-only, so the report did not receive the original Stage 1–5 rows even though the project contained full sibling manifests.

## Fix

`src/handgrip_analysis/stage6_report.py` now resolves report context in this order:

1. Use Stage 1–5 rows already present in the active manifest.
2. Load an explicit `stage_context_manifest` if provided.
3. Auto-discover sibling/full manifests from the capture-path project layout, including:
   - `data/manifests/all_runnable_manifest.csv`
   - `data/manifests/analysis_stages_1_4_manifest.csv`
   - `data/calibration_manifest.csv`
4. Fall back to filename-based original-stage inference for Stage 6 rows that reuse captures such as `*_stage2_*` or `*_stage4_*`.

## New optional CLI override

```bash
ha-stage stage=stage6 \
  manifest=data/manifests/stage6_filter_review_manifest.csv \
  outdir=data/analysis_results/stage6 \
  filter_config=conf/filters/candidates.yaml \
  stage_context_manifest=data/manifests/all_runnable_manifest.csv
```

The explicit override is optional when the standard project layout is used.

## Validation

Validated with a Stage 6-only manifest:

```bash
PYTHONPATH=src python -m handgrip_analysis.cli \
  stage=stage6 \
  manifest=data/manifests/stage6_filter_review_manifest.csv \
  outdir=/tmp/ha_stage6_context_fix \
  filter_config=conf/filters/candidates.yaml
```

The report now includes Stage 1, Stage 2, Stage 3, and Stage 4 insights. Stage 5 remains unavailable when no Stage 5 interference trials exist, which is expected.

Full test suite:

```text
65 passed
```
