# Handgrip Analysis Development Guide

## Summary

- Use this guide when adding an analysis stage, metric, filter family, plot, or report section.
- Keep stage math separate from CLI parsing and file IO where practical.
- Every new analysis feature should include config, tests, output documentation, and interpretation guidance.

## Add a new stage

### Files to edit

| File area                                            | Purpose                             |
| ---------------------------------------------------- | ----------------------------------- |
| `src/handgrip_analysis/...` or `scripts/stageN_*.py` | Stage implementation.               |
| `conf/analysis/stageN.yaml`                          | Stage defaults.                     |
| `Handgrip_Analysis/docs/stages.md`                   | Purpose/input/output documentation. |
| `Handgrip_Analysis/docs/configuration.md`            | Config reference.                   |
| `Handgrip_Analysis/docs/reports-and-outputs.md`      | Output artifacts.                   |
| `tests/`                                             | Unit/integration coverage.          |

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

### Files to edit

| Area                    | Purpose                                             |
| ----------------------- | --------------------------------------------------- |
| DSP/filter module       | Apply candidate filter.                             |
| filter candidate config | Add family/order/cutoff parameters.                 |
| Stage 6 runner          | Include candidate in benchmark loop.                |
| Stage 6 report          | Show metrics and interpretation.                    |
| tests                   | Validate frequency constraints and output behavior. |

### Required validation

- cutoff below Nyquist,
- stable coefficients,
- identity/raw baseline included,
- peak/rise/release distortion measured,
- latency/phase behavior documented,
- deployment target stated.

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

Suggested commands:

```bash
cd Handgrip_Analysis
uv run pytest
uv run ha-run-all --help
uv run ha-stage --help
```

## Documentation update checklist

- [ ] `docs/stages.md` updated if stage behavior changes.
- [ ] `docs/configuration.md` updated for new config keys.
- [ ] `docs/filter-design.md` updated for new filter family or Stage 6 metric.
- [ ] `docs/reports-and-outputs.md` updated for new artifacts.
- [ ] Root `docs/workflows/handgrip-analysis.md` still matches CLI usage.
- [ ] Generated examples remain under `docs/examples/analysis-output/` if curated.
