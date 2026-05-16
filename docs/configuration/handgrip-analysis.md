# Handgrip Analysis Configuration Reference

**Status:** Canonical root configuration reference  
**Component:** `Handgrip_Analysis`  
**Detailed component doc:** `Handgrip_Analysis/docs/configuration.md`  
**Config sources:** `Handgrip_Analysis/conf/**/*.yaml`

## Summary

Analysis config selects inputs, manifests, output roots, stages, DSP assumptions, filter candidates, aggregation behavior, validation splits, and report output. Stage 6 filter recommendations must be interpreted as evidence-backed proposals, not automatic deployment changes.

## Configuration table

| Key | Type | Default | Allowed range / values | Operational impact | When to change | Failure risk |
| --- | ---- | ------- | ---------------------- | ------------------ | -------------- | ------------ |
| `hydra.run.dir` | path template | `outputs/${now:%Y-%m-%d_%H-%M-%S}` | Writable Hydra path template. | Per-run output directory. | To centralize or disable timestamped outputs. | Hard-to-find outputs or overwrites. |
| `logging.level` | string | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`. | CLI/log verbosity. | Debug analysis pipeline. | Too much/little diagnostics. |
| `input` | path/null | `null` | CSV/session file. | Single-input analyses. | Running one stage on one file. | Missing input error. |
| `inputs` | list[path] | empty | List of CSV/session files. | Multi-input analyses. | Aggregate multiple trials. | Wrong trial set. |
| `manifest` | path/null | `null` | CSV manifest path. | Structured multi-stage run. | Production analysis. | Wrong/missing columns. |
| `base_outdir` / `outdir` | path/null | `null` | Writable output root. | Stage report/output location. | Study/session organization. | Outputs overwritten or scattered. |
| `trials.manifest` | path/null | `null` | Trial manifest. | Trial grouping/provenance. | Multi-trial statistics. | Aggregation over wrong trials. |
| `trials.min_trials_recommended` | int | `5` | Positive integer. | Quality guidance for aggregated inference. | Study sample-size policy. | Overconfidence with few trials. |
| `trials.min_trials_allowed` | int | `2` | Positive integer. | Minimum accepted trial count. | Smoke tests vs production. | Analysis runs with inadequate data. |
| `aggregation.statistic` | string | `median` | `median`, `mean`, supported statistic. | Summary statistic. | Change robustness policy. | Outliers dominate or hide effects. |
| `aggregation.bootstrap_resamples` | int | `5000` | Nonnegative integer. | Confidence interval precision/cost. | Speed vs precision tradeoff. | Slow runs or unstable intervals. |
| `stage1.ready_time_policy` | string | `p90_plus_margin` | Supported policy. | Startup/warm-up ready-time estimate. | Change warm-up criterion. | Wrong readiness estimate. |
| `stage1.guard_margin_s` | float | `30.0` | Nonnegative seconds. | Safety margin after warm-up estimate. | Hardware stabilization policy. | Too short/long readiness guard. |
| `stage2.psd_average` | string | `median` | PSD averaging policy. | Stationary noise PSD. | Change robustness against outliers. | Misleading spectral peaks. |
| `stage4.align_dynamic_trials_by` | string | `onset_10pct` | Supported alignment method. | Event overlay/comparison. | Different onset policy. | Distorted dynamic comparisons. |
| `stage6.validation.split_by` | string | `session_id` | Metadata column. | Train/validation grouping. | Study design. | Data leakage if split wrong. |
| `stage6.validation.fallback` | string | `leave_one_trial_out` | Supported fallback. | Validation when split metadata missing. | Small datasets. | Over-optimistic filter selection. |
| `stage6.constraints.max_peak_relative_error` | float | `0.03` | Nonnegative fraction. | Filter acceptance. | Stricter/looser fidelity. | Too permissive/restrictive candidate acceptance. |
| `stage6.constraints.max_peak_time_shift_s` | float | `0.025` | Nonnegative seconds. | Phase/latency acceptance. | Timing policy changes. | Laggy filter accepted. |
| `filters.metadata.target_sampling_rate_hz_observed` | float | `100.0` | Observed Hz. | Filter design frequency normalization. | New acquisition rate. | Invalid cutoff assumptions. |
| `filters.filters` | list[map] | 21 active candidates | Supported filter specs. | Candidate bank for Stage 6. | Add/retire filter families. | Candidate bank too broad/narrow. |
| `diagnostic_candidates_not_active` | map | diagnostic filters excluded | Candidate definitions kept inactive. | Preserve rejected alternatives. | Re-test high-pass/notch/band-pass. | Accidental deployment of diagnostic-only filters. |
