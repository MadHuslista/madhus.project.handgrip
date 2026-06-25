# Handgrip Analysis Development Guide

## Summary

- Use this guide when adding an analysis stage, metric, filter family, plot, or report section.
- Keep stage math separate from CLI parsing and file IO where practical.
- Every new analysis feature should include config, tests, output documentation, and interpretation guidance.

## Add a new stage

### Files to edit

| File area                                                                 | Purpose                             |
| ------------------------------------------------------------------------- | ----------------------------------- |
| `src/handgrip_analysis/...` or `scripts/stageN_*.py`                      | Stage implementation.               |
| `conf/analysis/stageN.yaml`                                               | Stage defaults.                     |
| [Handgrip_Analysis/docs/stages.md](stages.md)                           | Purpose/input/output documentation. |
| [Handgrip_Analysis/docs/configuration.md](configuration.md)             | Config reference.                   |
| [Handgrip_Analysis/docs/reports-and-outputs.md](reports-and-outputs.md) | Output artifacts.                   |
| `tests/`                                                                  | Unit/integration coverage.          |

### Required contract

A stage must document:

- required input columns,
- config keys,
- metrics produced,
- figures produced,
- interpretation rule,
- stop/failure conditions.

## Add a metric

### Steps

1. Implement the metric in the core/metrics layer.
2. Add unit tests with synthetic data.
3. Add the metric to the relevant stage result object/table.
4. Add report interpretation.
5. Add config threshold only if the threshold is user-tunable.

### Avoid

- metrics that silently depend on global sampling assumptions,
- metrics that produce unitless values without explanation,
- metrics shown in reports without interpretation.

## Add a filter family

Stage 6 only ranks production-real-time filters that are deployable in `LSL_Bridge`. A new active
filter is therefore a **cross-component** change: it must exist as a causal real-time node in
`LSL_Bridge` before `Handgrip_Analysis` can rank it. Offline-only filters (notch, high/band-pass,
moving-average, median, chain) stay as inactive diagnostic metadata only.

### Process

1. Implement the filter as a causal real-time node in `LSL_Bridge` (`src/lsl_bridge/core/filter.py`) and add it to `SUPPORTED_PRODUCTION_FILTER_TYPES`.
2. Mirror the same causal, per-sample implementation in `Handgrip_Analysis` (`src/handgrip_analysis/dsp.py`) and register it in `PRODUCTION_REALTIME_FILTER_TYPES`; extend `lsl_bridge_filter_config_from_spec()` so the type converts to an `LSL_Bridge` stanza.
3. Add the candidate to the active `filters:` list in `conf/filters/candidates.yaml` with production params (`cutoff_hz`, `sample_rate_hz`, `q`, `reset_on_gap_s`, `min_dt_s` as applicable).
4. Add equivalence tests proving the Analysis output matches the `LSL_Bridge` output sample-for-sample, plus the bridge-side filter test (`LSL_Bridge/tests/unit/test_filter.py`).
5. Re-run Stage 6 and update the Stage 6 report/recommendation.

### Required validation

- cutoff below Nyquist,
- stable coefficients,
- causal per-sample behavior equivalent to the `LSL_Bridge` node,
- identity/raw baseline included,
- peak/rise/release distortion measured,
- latency/phase behavior documented,
- converts cleanly through `lsl_bridge_filter_config_from_spec()` (active candidates that do not are rejected at config load).

## Add a report section

### Steps

1. Define what decision the section supports.
2. Add required metrics/figures.
3. Keep summary-first wording.
4. Link source input/config/run ID.
5. Add a test or snapshot check if the report format is stable.

### Required report structure

```markdown
## <Section>

### Conclusion
### Evidence
### Interpretation
### Limitations
### Next validation step
```

## Add a plot

A plot should include:

- title,
- x/y labels and units,
- raw/filtered/calibrated labels,
- source session/file ID,
- figure filename that maps to report text.

Do not add plots that are not referenced in a report or interpretation workflow.

## Testing strategy

| Test class        | Purpose                                                 |
| ----------------- | ------------------------------------------------------- |
| Unit tests        | Metrics, DSP functions, filter candidate validation.    |
| Integration tests | Stage run on small fixture data.                        |
| CLI tests         | Entry points, argument parsing, output folder creation. |
| Report tests      | Required sections/artifacts present.                    |

Suggested commands (run from the repo root or from `Handgrip_Analysis/` —
both resolve `data/...`/`conf/...` paths under `Handgrip_Analysis/`):

```bash
uv run pytest
uv run ha-run-all --help
uv run ha-stage --help
```

Note: `uv run pytest` must be run from `Handgrip_Analysis/` (pytest discovers
`tests/` relative to cwd).

## Documentation update checklist

- [ ] [Handgrip_Analysis/docs/stages.md](stages.md) updated if stage behavior changes.
- [ ] `docs/configuration.md` updated for new config keys.
- [ ] [Handgrip_Analysis/docs/filter-design.md](filter-design.md) updated for new filter family or Stage 6 metric.
- [ ] `docs/reports-and-outputs.md` updated for new artifacts.
- [ ] Root [docs/workflows/handgrip-analysis.md](../../docs/workflows/handgrip-analysis.md) still matches CLI usage.
- [ ] Generated examples remain under `docs/examples/analysis-output/` if curated.
