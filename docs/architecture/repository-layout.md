# Repository Layout

## Summary

- The repository is a multi-component suite, not a single script.
- Python components use a source-layout package style: runtime code lives under each component's `src/<package>/` directory.
- Root docs explain system-level workflows and contracts; component docs explain local implementation details.

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

The `src/` layout is the current best practice for Python projects. It prevents import errors and ensures that tests run against the installed package, not the local source files.
More details: 
    - [Python Packaging User Guide: src layout vs flat layout](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/)
    - [Python Project Structure: Why the ‘src’ Layout Beats Flat Folders (and How to Use My Free Template)](https://medium.com/@adityaghadge99/python-project-structure-why-the-src-layout-beats-flat-folders-and-how-to-use-my-free-template-808844d16f35)

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
├── workflow.md         - How to use this component in a typical workflow.
├── configuration.md    - How to configure this component, including config file format and options.
├── architecture.md     - Implementation details, data contracts, and design decisions.
└── development.md      - How to extend or modify this component, including code structure and style guidelines.
```

## Related docs: 
- [`docs/development/python-project-structure-primer.md`](../development/python-project-structure-primer.md),
- [`docs/index.md`](../index.md) files
