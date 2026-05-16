# Analysis Pipeline Troubleshooting

**Status:** Canonical symptom-first troubleshooting doc  
**Symptoms covered:** Manifest errors, missing stage outputs, invalid filter candidates  
**Related docs:** `docs/workflows/handgrip-analysis.md`, `Handgrip_Analysis/docs/stages.md`, `Handgrip_Analysis/docs/filter-design.md`

## Summary

Use this guide when `Handgrip_Analysis` cannot load inputs, run stages, or produce expected reports/filter recommendations.

## Symptom: manifest errors

### Likely causes

| Cause | Check | Fix |
| --- | --- | --- |
| Source file missing | manifest paths | Use repo-relative or component-relative paths consistently. |
| Column name mismatch | input CSV headers | Update manifest channel mapping. |
| Wrong session ID | manifest/session folder | Copy exact session ID from calibration output. |
| Unsupported data type | loader errors | Convert/export to expected CSV/session format. |
| Missing protocol metadata | report cannot group trials | Use calibration session with event markers. |

## Symptom: missing stage outputs

### Likely causes

| Cause | Fix |
| --- | --- |
| Stage disabled in config | Enable stage or run specific stage command. |
| Output directory changed | Inspect config and command override. |
| Stage failed silently in batch | Run stage individually with verbose logging. |
| Required input absent | Fix manifest or upstream export. |
| Old output read by mistake | Delete/rename output folder or use new run ID. |

## Symptom: invalid filter candidates

### Common causes

| Cause | Explanation | Fix |
| --- | --- | --- |
| Cutoff above Nyquist | Sampling rate too low for requested cutoff | Lower cutoff or confirm sampling rate. |
| Missing raw baseline | Candidate comparison lacks reference | Include identity/raw candidate. |
| Filter unstable | Bad order/cutoff/family combination | Use validated filter families. |
| Latency not considered | Smooth trace but bad timing | Include lag/phase metrics. |
| Recommendation target unclear | Unsure whether to apply in bridge/viewer/firmware | Document deployment target in Stage 6 report. |

## Diagnostic workflow

1. Run `--help` for available CLI entry points:

```bash
cd Handgrip_Analysis
uv run ha-run-all --help
uv run ha-stage --help
uv run ha-stage6 --help
```

2. Validate manifest file paths.
3. Run the failing stage individually.
4. Inspect logs/output folder.
5. Check required columns and sampling rate.
6. For Stage 6, inspect candidate table and recommendation file.

## Expected Stage 6 artifacts

Typical artifacts include:

- `filter_comparison.csv`,
- `metrics.json`,
- Stage 6 report Markdown/HTML,
- plots,
- `lsl_bridge_processing_recommendation.yaml` or equivalent recommendation file.

## Stop conditions

Do not apply filter recommendations if:

- input sampling rate is uncertain,
- candidate comparison omitted raw baseline,
- latency/phase behavior was not considered,
- recommendation target is ambiguous,
- calibration residuals were not rechecked after applying a processing change.

## Validation commands

```bash
rg 'Stage 6|filter design|lsl_bridge_processing_recommendation.yaml' Handgrip_Analysis/docs docs/examples/analysis-output/README.md
rg 'ha-run-all|ha-stage|ha-stage6' Handgrip_Analysis/docs/quickstart.md Handgrip_Analysis/docs/development.md
```
