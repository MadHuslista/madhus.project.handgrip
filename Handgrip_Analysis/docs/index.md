# Handgrip Analysis Documentation

## Summary

- **Purpose:** Offline signal-analysis and filter-design pipeline for captured handgrip data.
- This page is the component-level documentation map.
- Start here when you know this component is the one you need, then follow the specific workflow/configuration/architecture links.
- Some linked files are created in later phases of the documentation refactor; this index defines the intended stable navigation structure.

## Audience

| Reader                | Use this page to...                                                            |
| --------------------- | ------------------------------------------------------------------------------ |
| Operator              | Find the minimal run/validation workflow for this component.                   |
| Maintainer            | Find configuration and architecture references before editing code.            |
| Student developer     | Learn where behavior lives and which tests/validation steps should be updated. |
| External collaborator | Understand this component's boundary within the full Handgrip Suite.           |

## Component contract

- Analysis is file-based and can be run after acquisition/calibration data exists.
- Generated analysis outputs should be treated as results/examples, not as maintained documentation.
- Stage 6 filter recommendations should be validated before deployment to the live acquisition path.

## Documentation map

| Document                                           | Purpose                                                        |
| -------------------------------------------------- | -------------------------------------------------------------- |
| [`quickstart.md`](quickstart.md)                   | Run basic stages and understand required inputs.               |
| [`stages.md`](stages.md)                           | Stage 1–6 purpose, input, output, and interpretation.          |
| [`configuration.md`](configuration.md)             | Full `conf/**/*.yaml` configuration reference.                 |
| [`filter-design.md`](filter-design.md)             | Candidate filter review/design workflow and recommendations.   |
| [`reports-and-outputs.md`](reports-and-outputs.md) | Output tree, reports, figures, metrics, examples.              |
| [`architecture.md`](architecture.md)               | CLI, stage modules, IO, DSP, reporting layers.                 |
| [`development.md`](development.md)                 | How to add stages, metrics, plots, filter families, and tests. |

## Related system docs

| System doc                                                                                   | Why it matters                                        |
| -------------------------------------------------------------------------------------------- | ----------------------------------------------------- |
| [`../../docs/start-here.md`](../../docs/start-here.md)                                       | High-level introduction to the full suite.            |
| [`../../docs/system-overview.md`](../../docs/system-overview.md)                             | Physical/software/dataflow map.                       |
| [`../../docs/architecture/stream-contracts.md`](../../docs/architecture/stream-contracts.md) | Cross-component stream and IPC contracts.             |
| [`../../docs/configuration/index.md`](../../docs/configuratiwon/index.md)                    | Configuration ownership and cross-component settings. |
| [`../../docs/troubleshooting/index.md`](../../docs/troubleshooting/index.md)                 | Symptom-first debugging entry point.                  |

## Validation checklist for this docs index

- [ ] The README links to this `docs/index.md`.
- [ ] Every linked component doc exists by the end of the relevant documentation phase.
- [ ] Component-specific docs link back to root system contracts where applicable.
- [ ] Configuration docs include default, type/range, impact, safe-edit guidance, and failure modes.
- [ ] Development docs identify files to edit, tests to update, and validation gates.
