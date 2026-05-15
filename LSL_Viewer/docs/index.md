# LSL Viewer Documentation

## Summary

- **Purpose:** Browser-based viewer for live LSL streams and CSV/XDF replay, including time-series and XY correlation plots.
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

- `LSL_Viewer` is an observer/diagnostic tool, not the acquisition authority.
- Browser render downsampling must not be confused with acquisition or saved-data downsampling.
- The XY correlation view depends on correct stream timestamp alignment.

## Documentation map

| Document                                         | Purpose                                                              |
| ------------------------------------------------ | -------------------------------------------------------------------- |
| [`quickstart.md`](quickstart.md)                 | Start viewer and inspect target/reference streams.                   |
| [`configuration.md`](configuration.md)           | Full `conf/config.yaml` reference.                                   |
| [`xy-correlation.md`](xy-correlation.md)         | XY plot behavior, alignment, lag diagnosis, and lock modes.          |
| [`live-csv-xdf-modes.md`](live-csv-xdf-modes.md) | Live mode, CSV replay, XDF replay, and validation mode.              |
| [`architecture.md`](architecture.md)             | Stream buffers, UI refresh model, rendering/downsampling boundaries. |
| [`development.md`](development.md)               | How to add plots, controls, channels, and tests.                     |

## Related system docs

| System doc                                                                                   | Why it matters                                        |
| -------------------------------------------------------------------------------------------- | ----------------------------------------------------- |
| [`../../docs/start-here.md`](../../docs/start-here.md)                                       | High-level introduction to the full suite.            |
| [`../../docs/system-overview.md`](../../docs/system-overview.md)                             | Physical/software/dataflow map.                       |
| [`../../docs/architecture/stream-contracts.md`](../../docs/architecture/stream-contracts.md) | Cross-component stream and IPC contracts.             |
| [`../../docs/configuration/index.md`](../../docs/configuration/index.md)                     | Configuration ownership and cross-component settings. |
| [`../../docs/troubleshooting/index.md`](../../docs/troubleshooting/index.md)                 | Symptom-first debugging entry point.                  |

## Validation checklist for this docs index

- [ ] The README links to this `docs/index.md`.
- [ ] Every linked component doc exists by the end of the relevant documentation phase.
- [ ] Component-specific docs link back to root system contracts where applicable.
- [ ] Configuration docs include default, type/range, impact, safe-edit guidance, and failure modes.
- [ ] Development docs identify files to edit, tests to update, and validation gates.
