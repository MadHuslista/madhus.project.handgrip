# Repository Layout

**Status:** Canonical root architecture document  
**Audience:** Maintainers, student developers, and future collaborators  
**Scope:** How the repository is organized and where to edit safely  
**Related docs:** [`docs/development/python-project-structure-primer.md`](../development/python-project-structure-primer.md), component [`docs/index.md`](../index.md) files

## Summary

- The repository is a multi-component suite, not a single script.
- Python components use a source-layout package style: runtime code lives under each component's `src/<package>/` directory.
- Root docs explain system-level workflows and contracts; component docs explain local implementation details.
- Generated data, logs, and reports are not canonical documentation unless explicitly curated under `docs/examples/`.

## Top-level layout

```text
handgrip-suite/
├── README.md
├── pyproject.toml
├── platformio.ini
├── docs/
├── Handgrip_Firmware/
├── RS485_GUI/
├── LSL_Bridge/
├── LSL_Viewer/
├── Handgrip_Calibration/
└── Handgrip_Analysis/
```

## Component responsibilities

| Path                    | Type                          | Responsibility                                             | First doc                                                                |
| ----------------------- | ----------------------------- | ---------------------------------------------------------- | ------------------------------------------------------------------------ |
| `Handgrip_Firmware/`    | PlatformIO / Arduino firmware | Target handgrip data acquisition and D2 UART stream        | [`Handgrip_Firmware/README.md`](../../Handgrip_Firmware/README.md)       |
| `RS485_GUI/`            | Python application            | Reference-board acquisition, GUI, logs, ZMQ IPC            | [`RS485_GUI/README.md`](../../RS485_GUI/README.md)                       |
| `LSL_Bridge/`           | Python application            | Publish target/reference LSL streams                       | [`LSL_Bridge/README.md`](../../LSL_Bridge/README.md)                     |
| `LSL_Viewer/`           | Python application            | Live/replay visualization and XY correlation               | [`LSL_Viewer/README.md`](../../LSL_Viewer/README.md)                     |
| `Handgrip_Calibration/` | Python CLI package            | Calibration sessions, fitting, reports, holdout validation | [`Handgrip_Calibration/README.md`](../../Handgrip_Calibration/README.md) |
| `Handgrip_Analysis/`    | Python CLI package            | Offline analysis stages and filter design                  | [`Handgrip_Analysis/README.md`](../../Handgrip_Analysis/README.md)       |
| `docs/`                 | Markdown documentation        | Canonical system docs                                      | [`docs/index.md`](../index.md)                                           |

## Where to edit

| Goal                                   | Edit here first                                                                                                   | Do not start here                   |
| -------------------------------------- | ----------------------------------------------------------------------------------------------------------------- | ----------------------------------- |
| Change firmware serial schema          | `Handgrip_Firmware/Core/Inc/config.h`, firmware protocol docs, bridge parser tests                                | Viewer/calibration code only.       |
| Change reference-board serial settings | `RS485_GUI/config/config.yaml`, acquisition-board docs                                                            | LSL viewer config.                  |
| Change LSL stream names/channels       | `LSL_Bridge/conf/config.yaml`, [`docs/architecture/stream-contracts.md`](stream-contracts.md), downstream configs | One consumer only.                  |
| Change viewer plot behavior            | `LSL_Viewer/conf/config.yaml`, viewer docs, viewer source                                                         | Bridge or firmware.                 |
| Add calibration protocol               | `Handgrip_Calibration/conf/protocol_*.yaml`, calibration protocol docs, tests                                     | Hard-coded CLI logic unless needed. |
| Add analysis stage                     | `Handgrip_Analysis/src/handgrip_analysis/`, analysis docs, tests                                                  | Generated output folders.           |

## Python source-layout pattern

Typical Python component:

```text
Component_Name/
├── pyproject.toml
├── README.md
├── conf/ or config/
├── docs/
├── src/
│   └── package_name/
│       ├── __init__.py
│       └── ...
└── tests/
```

The `src/` layout prevents accidental imports from the working directory and makes tests more representative of installed behavior.

## Documentation layout

Root-level docs:

```text
docs/
├── architecture/
├── workflows/
├── hardware/
├── configuration/
├── development/
├── troubleshooting/
└── examples/
```

Component-level docs:

```text
<Component>/docs/
├── index.md
├── workflow.md
├── configuration.md
├── architecture.md
└── development.md
```

## Generated data and outputs

Generated outputs belong in component data/output directories, not in canonical docs. If an output is useful for teaching, curate a small excerpt under `docs/examples/` and explicitly label it as an example.

## Validation checklist

- [ ] Every component has [`README.md`](../../README.md).
- [ ] Every component has [`docs/index.md`](../index.md).
- [ ] Root [`docs/index.md`](../index.md) links to all major workflows.
- [ ] Root architecture docs link to component docs instead of duplicating implementation details.
- [ ] Generated outputs are not presented as maintained instructions.
