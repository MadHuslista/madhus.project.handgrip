# RS485 GUI Documentation

## Summary

- **Purpose:** Python/NiceGUI app for acquisition-board communication, live plotting, logging, and ZeroMQ IPC publishing.
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

- `RS485_GUI` is the reference-chain acquisition owner.
- It should be started before `LSL_Bridge` in the full live workflow.
- Its IPC topic is expected to be consumed by `LSL_Bridge`.
- Its canonical config path is `RS485_GUI/config/config.yaml`.

## Documentation map

| Document                                                 | Purpose                                                    |
| -------------------------------------------------------- | ---------------------------------------------------------- |
| [`quickstart.md`](quickstart.md)                         | Run the GUI and verify acquisition-board communication.    |
| [`configuration.md`](configuration.md)                   | Full `config/config.yaml` reference.                       |
| [`active-send-and-modbus.md`](active-send-and-modbus.md) | Modbus RTU polling vs vendor Active-Send behavior.         |
| [`ipc-schema.md`](ipc-schema.md)                         | ZeroMQ topic, payload fields, aliases, and consumers.      |
| [`logging-and-outputs.md`](logging-and-outputs.md)       | CSV/NDJSON/event logs and output retention.                |
| [`architecture.md`](architecture.md)                     | Core/transport/io/ui/config layer map.                     |
| [`development.md`](development.md)                       | How to add parser fields, UI controls, loggers, and tests. |

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
