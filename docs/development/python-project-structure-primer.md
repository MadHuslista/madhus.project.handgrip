# Python Project Structure Primer

**Status:** Canonical development primer  
**Audience:** Research Python users, student maintainers, and future contributors  
**Scope:** Repository layout, Python source-layout packages, editable installs, entry points, tests, configs, and safe run/edit workflow  
**Related docs:** [`docs/architecture/repository-layout.md`](../architecture/repository-layout.md), [`docs/configuration/index.md`](../configuration/index.md), component `docs/development.md` files

## Summary

- The Handgrip Suite is a **multi-component repository**, not a single script folder.
- Python application code lives under each component's `src/<package_name>/` directory.
- The root `pyproject.toml` installs local packages as editable dependencies so changes in the repo are used immediately by `uv run ...` commands.
- Do not edit installed packages inside `.venv/` or global `site-packages`; edit the repo source files instead.
- Prefer running commands from the repo root for workspace-level setup, then from component roots when a component workflow expects local config paths.

## Repo root vs component root

The repository root is the folder that contains:

```text
README.md
pyproject.toml
platformio.ini
docs/
Handgrip_Firmware/
RS485_GUI/
LSL_Bridge/
LSL_Viewer/
Handgrip_Calibration/
Handgrip_Analysis/
```

A component root is one of the component folders, for example:

```text
RS485_GUI/
LSL_Bridge/
LSL_Viewer/
Handgrip_Calibration/
Handgrip_Analysis/
```

Use the repo root for:

- `uv sync`,
- workspace-level `uv run pytest`,
- root documentation validation,
- cross-component grep checks,
- firmware PlatformIO config from `platformio.ini`.

Use a component root for:

- component-local configs such as `conf/config.yaml` or `config/config.yaml`,
- examples that explicitly use relative config paths,
- component-specific tests,
- operator workflows that assume paths relative to that component.

## `src/` layout

Most Python components use a source-layout package pattern:

```text
<Component>/
├── pyproject.toml
├── README.md
├── docs/
├── conf/ or config/
├── src/
│   └── <package_name>/
│       ├── __init__.py
│       └── ...
└── tests/
```

This means importable code is not placed directly at the component root. It is placed under `src/` so tests and commands behave closer to an installed package.

Example:

```text
LSL_Bridge/src/lsl_bridge/
RS485_GUI/src/rs485_gui/
LSL_Viewer/src/lsl_viewer/
Handgrip_Calibration/src/handgrip_calibration/
```

## Editable installs

Editable installs let `uv run ...` use code directly from the repo. When you edit a source file under `src/`, you do not need to manually copy code into the environment.

Recommended workspace setup:

```bash
uv sync
```

Then run commands with:

```bash
uv run <command>
```

Examples:

```bash
uv run rs485-gui --help
uv run lsl-bridge --help
uv run lsl-viewer --help
uv run handgrip-cal --help
```

## `pyproject.toml`

Each Python component can have its own `pyproject.toml`, and the repo root also has a workspace-level `pyproject.toml`.

Use `pyproject.toml` to understand:

- package name,
- CLI entry points,
- dependencies,
- optional dev dependencies,
- test configuration,
- local editable package references.

Do not duplicate dependency installation instructions in random docs. Link to the component README or root setup docs instead.

## Entry points

Entry points are CLI commands installed by the package metadata. They are safer than running files directly because they exercise the package as installed.

| Component              | Typical entry point                                        | Purpose                                      |
| ---------------------- | ---------------------------------------------------------- | -------------------------------------------- |
| `RS485_GUI`            | `uv run rs485-gui`                                         | Reference-board GUI, logging, IPC publisher. |
| `LSL_Bridge`           | `uv run lsl-bridge`                                        | Publish target/reference LSL streams.        |
| `LSL_Viewer`           | `uv run lsl-viewer`                                        | Live/CSV/XDF viewer.                         |
| `Handgrip_Calibration` | `uv run handgrip-cal ...`                                  | Preflight, record, fit, report, validate.    |
| `Handgrip_Analysis`    | `uv run ha-run-all`, `uv run ha-stage`, `uv run ha-stage6` | Offline analysis stages and filter design.   |

If an entry point fails, check the component `pyproject.toml` and component README before running internal module files directly.

## Tests

Tests should be run before and after structural changes.

Workspace-level:

```bash
uv run pytest
```

Component-level examples:

```bash
cd LSL_Bridge
uv run pytest tests/unit/test_parser.py
uv run pytest tests/unit/test_timestamping.py
```

```bash
cd Handgrip_Calibration
uv run pytest
```

```bash
cd Handgrip_Analysis
uv run pytest
```

## Configs

Configuration is component-owned.

| Component   | Main config path                                        | Docs                                                                                             |
| ----------- | ------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| Firmware    | `platformio.ini`, `Handgrip_Firmware/Core/Inc/config.h` | [`Handgrip_Firmware/docs/configuration.md`](../../Handgrip_Firmware/docs/configuration.md)       |
| RS485 GUI   | `RS485_GUI/config/config.yaml`                          | [`RS485_GUI/docs/configuration.md`](../../RS485_GUI/docs/configuration.md)                       |
| LSL Bridge  | `LSL_Bridge/conf/config.yaml`                           | [`LSL_Bridge/docs/configuration.md`](../../LSL_Bridge/docs/configuration.md)                     |
| LSL Viewer  | `LSL_Viewer/conf/config.yaml`                           | [`LSL_Viewer/docs/configuration.md`](../../LSL_Viewer/docs/configuration.md)                     |
| Calibration | `Handgrip_Calibration/conf/*.yaml`                      | [`Handgrip_Calibration/docs/configuration.md`](../../Handgrip_Calibration/docs/configuration.md) |
| Analysis    | `Handgrip_Analysis/conf/**/*.yaml`                      | [`Handgrip_Analysis/docs/configuration.md`](../../Handgrip_Analysis/docs/configuration.md)       |

If a config change affects stream names, channel names, serial schema, or calibration semantics, also update:

- [`docs/architecture/stream-contracts.md`](../architecture/stream-contracts.md),
- relevant component docs,
- tests or validation scripts,
- example workflow docs.

## Why not edit installed `site-packages`

Do not edit code under:

```text
.venv/lib/python*/site-packages/
/usr/lib/python*/site-packages/
~/.local/lib/python*/site-packages/
```

Reasons:

- changes are not version-controlled,
- changes disappear on reinstall,
- other developers cannot reproduce them,
- tests may use different code than expected,
- handoff becomes impossible to audit.

Edit repo files under `src/` and commit those changes.

## How to run from repo root

Recommended baseline:

```bash
# From repo root
uv sync
uv run pytest
```

For full live workflow, open separate terminals:

```bash
# Terminal 1
cd RS485_GUI
uv run rs485-gui

# Terminal 2
cd LSL_Bridge
uv run lsl-bridge

# Terminal 3
cd LSL_Viewer
uv run lsl-viewer
```

For calibration:

```bash
cd Handgrip_Calibration
uv run handgrip-cal preflight --config conf/protocol_static_reversible_staircase_v3.yaml
```

For analysis:

```bash
cd Handgrip_Analysis
uv run ha-run-all --help
uv run ha-stage --help
```

## Safe editing rule

Before editing a component, answer:

1. Which component owns this behavior?
2. Which config controls it?
3. Which data contract is affected?
4. Which tests validate it?
5. Which documentation must change with it?

If the change crosses component boundaries, update root architecture docs and component docs in the same commit.
