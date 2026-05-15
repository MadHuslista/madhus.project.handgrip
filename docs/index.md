# Handgrip Suite Documentation Index

## Summary

- This is the main navigation page for the Handgrip Suite documentation.
- Start with the reader pathway that matches your role, then follow the workflow or component-specific links.
- The documentation is organized from **operator workflows** to **architecture/configuration** to **implementation/development**.
- Some linked documents are intentionally created in later documentation-refactor phases. This index defines the final navigation structure.

## Reader pathways

| Reader / task                  | Start here                                                                                         | Then read                                                                                                                                                                              | Goal                                                                                  |
| ------------------------------ | -------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| I am new to the system         | [`start-here.md`](start-here.md)                                                                   | [`system-overview.md`](system-overview.md)                                                                                                                                             | Understand the purpose, hardware, software processes, and first workflow.             |
| I need to connect the hardware | [`workflows/physical-setup.md`](workflows/physical-setup.md)                                       | [`hardware/index.md`](hardware/index.md)                                                                                                                                               | Wire the PM58, acquisition board, target handgrip, RS485 adapter, and host PC safely. |
| I need to upload firmware      | [`workflows/firmware-setup.md`](workflows/firmware-setup.md)                                       | [`../Handgrip_Firmware/docs/index.md`](../Handgrip_Firmware/docs/index.md)                                                                                                             | Build/upload the Arduino Nano firmware and validate serial output.                    |
| I need to see live signals     | [`workflows/full-live-viewer-quickstart.md`](workflows/full-live-viewer-quickstart.md)             | [`../RS485_GUI/docs/index.md`](../RS485_GUI/docs/index.md), [`../LSL_Bridge/docs/index.md`](../LSL_Bridge/docs/index.md), [`../LSL_Viewer/docs/index.md`](../LSL_Viewer/docs/index.md) | Start the runtime processes and inspect signals.                                      |
| I need to run calibration      | [`workflows/handgrip-calibration.md`](workflows/handgrip-calibration.md)                           | [`../Handgrip_Calibration/docs/index.md`](../Handgrip_Calibration/docs/index.md)                                                                                                       | Record calibration data, fit/report models, and validate outputs.                     |
| I need to run analysis         | [`workflows/handgrip-analysis.md`](workflows/handgrip-analysis.md)                                 | [`../Handgrip_Analysis/docs/index.md`](../Handgrip_Analysis/docs/index.md)                                                                                                             | Characterize signals and evaluate filter candidates.                                  |
| I need to modify configs       | [`configuration/index.md`](configuration/index.md)                                                 | Component `docs/configuration.md` files                                                                                                                                                | Understand defaults, safe ranges, impact, and failure modes.                          |
| I need to modify code          | [`development/python-project-structure-primer.md`](development/python-project-structure-primer.md) | Component `docs/development.md` files                                                                                                                                                  | Understand source layout, entry points, tests, and extension patterns.                |
| Something is broken            | [`troubleshooting/index.md`](troubleshooting/index.md)                                             | Relevant symptom-specific page                                                                                                                                                         | Diagnose by symptom before editing code.                                              |

## Documentation layers

```text
README.md
  → docs/start-here.md
  → docs/system-overview.md
  → docs/workflows/*.md
  → component README.md
  → component docs/index.md
  → component workflow/configuration/architecture/development docs
```

Use the high-level docs to understand the system before editing component internals.

## Core documentation folders

| Folder                                 | Purpose                                                                                 | Owner                    |
| -------------------------------------- | --------------------------------------------------------------------------------------- | ------------------------ |
| [`architecture/`](architecture/)       | System architecture, dataflow, stream contracts, runtime processes, timing              | System maintainer        |
| [`workflows/`](workflows/)             | Operator procedures: physical setup, firmware setup, quickstarts, calibration, analysis | Operator + maintainer    |
| [`hardware/`](hardware/)               | PM58, acquisition board, HX711, force fixture, images, PDFs, source references          | Hardware maintainer      |
| [`configuration/`](configuration/)     | Cross-component config overview and per-component configuration references              | Component maintainers    |
| [`development/`](development/)         | Source-layout primer, testing, extension recipes, maintainability guidance              | Developer maintainer     |
| [`troubleshooting/`](troubleshooting/) | Symptom-first diagnosis pages                                                           | Operator + maintainer    |
| [`examples/`](examples/)               | Curated calibration and analysis output examples                                        | Documentation maintainer |
| [`contributing/`](contributing/)       | Documentation/report style and maintenance rules                                        | Documentation maintainer |
| [`archive/`](archive/)                 | Historical, planning, deprecated, or non-canonical material                             | Documentation maintainer |

## Component documentation

| Component              | Entry point                                                              | Component docs                                                                   | Primary responsibility                                             |
| ---------------------- | ------------------------------------------------------------------------ | -------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| `Handgrip_Firmware`    | [`../Handgrip_Firmware/README.md`](../Handgrip_Firmware/README.md)       | [`../Handgrip_Firmware/docs/index.md`](../Handgrip_Firmware/docs/index.md)       | Arduino/HX711 target data firmware.                                |
| `RS485_GUI`            | [`../RS485_GUI/README.md`](../RS485_GUI/README.md)                       | [`../RS485_GUI/docs/index.md`](../RS485_GUI/docs/index.md)                       | Reference-board GUI, logging, and IPC publisher.                   |
| `LSL_Bridge`           | [`../LSL_Bridge/README.md`](../LSL_Bridge/README.md)                     | [`../LSL_Bridge/docs/index.md`](../LSL_Bridge/docs/index.md)                     | Publishes target/reference streams to Lab Streaming Layer.         |
| `LSL_Viewer`           | [`../LSL_Viewer/README.md`](../LSL_Viewer/README.md)                     | [`../LSL_Viewer/docs/index.md`](../LSL_Viewer/docs/index.md)                     | Live and replay signal visualization.                              |
| `Handgrip_Calibration` | [`../Handgrip_Calibration/README.md`](../Handgrip_Calibration/README.md) | [`../Handgrip_Calibration/docs/index.md`](../Handgrip_Calibration/docs/index.md) | Calibration recording, fitting, report generation, and validation. |
| `Handgrip_Analysis`    | [`../Handgrip_Analysis/README.md`](../Handgrip_Analysis/README.md)       | [`../Handgrip_Analysis/docs/index.md`](../Handgrip_Analysis/docs/index.md)       | Offline signal analysis and filter-design workflows.               |

## Canonical system contracts

| Contract                     | Current expected value                                                   | Where it is documented in detail                                                                                                                                   |
| ---------------------------- | ------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Target LSL stream            | `HandgripTarget`                                                         | [`architecture/stream-contracts.md`](architecture/stream-contracts.md), [`../LSL_Bridge/docs/stream-contracts.md`](../LSL_Bridge/docs/stream-contracts.md)         |
| Reference LSL stream         | `HandgripReference`                                                      | [`architecture/stream-contracts.md`](architecture/stream-contracts.md), [`../LSL_Bridge/docs/stream-contracts.md`](../LSL_Bridge/docs/stream-contracts.md)         |
| RS485 GUI IPC topic          | `rs485.measurement.v1`                                                   | [`../RS485_GUI/docs/ipc-schema.md`](../RS485_GUI/docs/ipc-schema.md), [`../LSL_Bridge/docs/stream-contracts.md`](../LSL_Bridge/docs/stream-contracts.md)           |
| Firmware data frame          | `D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>`           | [`../Handgrip_Firmware/docs/serial-protocol.md`](../Handgrip_Firmware/docs/serial-protocol.md)                                                                     |
| Primary calibration protocol | `Handgrip_Calibration/conf/protocol_static_reversible_staircase_v3.yaml` | [`../Handgrip_Calibration/docs/protocols.md`](../Handgrip_Calibration/docs/protocols.md), [`workflows/handgrip-calibration.md`](workflows/handgrip-calibration.md) |

## Archive and reference policy

Use canonical docs for current procedures. Use archive/reference material only when you need source verification or historical context.

| Material type                        | Location                                           | Rule                                                     |
| ------------------------------------ | -------------------------------------------------- | -------------------------------------------------------- |
| Current procedures                   | `docs/workflows/`, component `docs/`               | Use for operation and handoff.                           |
| Hardware source manuals/PDFs         | `docs/hardware/references/`                        | Fallback reference, not first-reading material.          |
| Historical reports/plans             | `docs/archive/`                                    | Preserve context, do not use as current procedure.       |
| Deprecated HX710B / old MCU material | `docs/archive/deprecated/` or removed from package | Do not use for current wiring, firmware, or calibration. |
| Generated output examples            | `docs/examples/`                                   | Curated examples only, not canonical source of truth.    |
