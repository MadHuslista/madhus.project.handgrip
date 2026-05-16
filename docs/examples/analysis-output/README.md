# Curated Analysis Output Example

**Status:** Curated example, not canonical source data  
**Audience:** Maintainers and reviewers interpreting `Handgrip_Analysis` outputs  
**Source class:** Existing `Handgrip_Analysis/data/analysis_results/stage6/` outputs and filter-design report  
**Related docs:** `docs/workflows/handgrip-analysis.md`, `Handgrip_Analysis/docs/filter-design.md`, `Handgrip_Analysis/docs/reports-and-outputs.md`

## Summary

This directory is for small examples showing how to read analysis outputs, especially Stage 6 filter-design artifacts. Do not copy complete analysis output trees here unless intentionally curated.

## Stage 6 example interpretation

The current curated conclusion from prior Stage 6 work is:

- Keep the raw channel for traceability.
- Do not use continuous high-pass filtering as the primary force path.
- Do not use band-pass filtering as the primary force path.
- Notch filtering is not needed for the main product path if a modest low-pass already removes high-frequency contamination.
- Primary filtered channel recommendation: **2nd-order Butterworth low-pass at 15 Hz, fs = 100 Hz**.
- Optional secondary stable-display channel: **2nd-order Butterworth low-pass at 10 Hz, fs = 100 Hz**.
- Baseline/zero handling should be state-based tare/unloaded baseline tracking, not continuous high-pass filtering during grip events.

## Important Stage 6 artifacts

| Artifact | Purpose | How to use |
| --- | --- | --- |
| `stage6_review_design_report.md` | Human-readable review/design report. | Start here for reasoning and final recommendation. |
| `filter_acceptance_report.md` | Acceptance/failure analysis for candidates. | Check why candidates passed/failed constraints. |
| `filter_ranking_summary.csv` | Candidate ranking. | Inspect top candidates and composite scores. |
| `filter_validation_scores.csv` | Validation scores. | Check whether a filter generalizes across trials/sessions. |
| `filter_decision_summary.csv` | Compact decision table. | Use in handoff reports. |
| `filter_design_assessment.csv` | Per-candidate design assessment. | Audit filter tradeoffs. |
| `lsl_bridge_processing_recommendation.yaml` | Candidate deployment config for `LSL_Bridge`. | Copy only after validation and review. |
| `selected_filter_recommendation.json` | Machine-readable selected recommendation. | Preserve for reproducibility. |
| `figures/aggregate/stage6_design_representative_overlay.png` | Visual overlay of representative input/filter output. | Check waveform realism. |

## What not to do

- Do not deploy the smoothest-looking filter automatically.
- Do not remove the raw channel.
- Do not treat Stage 6 output as calibration proof; it is a signal-processing recommendation.
- Do not apply high-pass or band-pass filters to the primary force path unless a new validated analysis overturns the current evidence.

## Deployment review checklist

Before copying `lsl_bridge_processing_recommendation.yaml` into the live bridge config:

- [ ] Candidate filter is selected by Stage 6 evidence, not just appearance.
- [ ] Peak preservation and peak-time shift are acceptable.
- [ ] Rise-time / derivative behavior remains realistic.
- [ ] Hold stability improves or remains acceptable.
- [ ] Calibration residuals do not degrade after deployment.
- [ ] Raw data remains logged or streamable.

## Curation rule

This directory may contain short narrative excerpts and selected tables. Keep full generated output in `Handgrip_Analysis/data/analysis_results/`.
