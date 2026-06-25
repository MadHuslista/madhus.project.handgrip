# RS485 GUI Development Guide

## Summary

- This guide explains how to modify `RS485_GUI` without breaking the reference acquisition contract.
- Add behavior at the layer that owns it: parser fields in core/transport, UI controls in UI, logs in IO, config keys in config, and bridge payload changes in publisher/schema docs.
- Every change that affects `rs485.measurement.v1` must also update `LSL_Bridge` expectations and root [docs/architecture/stream-contracts.md](../../docs/architecture/stream-contracts.md).
- Prefer small pure-function changes with unit tests before modifying worker/UI side effects.

## Development setup

From `RS485_GUI/`:

```bash
uv sync --extra dev
uv run pytest
```

Useful targeted test commands:

```bash
uv run pytest tests/unit/test_codec.py
uv run pytest tests/unit/test_signals.py
uv run pytest tests/unit/test_config.py
uv run pytest tests/integration/test_active_send_parser.py
uv run pytest tests/integration/test_file_logger.py
uv run pytest tests/e2e/test_cli.py
```

## Source ownership map

| Task                       | Primary files                                                                   | Tests to update                                                            |
| -------------------------- | ------------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| Add decoded board field    | `core/codec.py`, possibly `transport/active_send.py` or `transport/modbus.py`   | `tests/unit/test_codec.py`, `tests/integration/test_active_send_parser.py` |
| Add plotted signal         | `core/signals.py`, possibly `ui/layout.py`                                      | `tests/unit/test_signals.py`                                               |
| Add IPC field              | `io/publisher.py`, [RS485_GUI/docs/ipc-schema.md](ipc-schema.md), root stream contracts | publisher/bridge tests if available                                        |
| Add log column/file field  | `io/logger.py`, [RS485_GUI/docs/logging-and-outputs.md](logging-and-outputs.md)         | `tests/integration/test_file_logger.py`                                    |
| Add UI control             | `ui/layout.py`, `state.py`, config if persistent                                | UI/e2e test if available; manual quickstart                                |
| Add config key             | `config/config.yaml`, `config/schema.py`, `docs/configuration.md`               | `tests/unit/test_config.py`                                                |
| Change Active-Send parser  | `transport/active_send.py`, `core/codec.py`                                     | `tests/integration/test_active_send_parser.py`                             |
| Change Modbus register map | `constants.py`, `config/config.yaml`, `transport/modbus.py`                     | `tests/unit/test_codec.py`, manual Modbus test                             |

## How to add a parser field

### Step 1 — Identify source register/bytes

- For Modbus RTU, inspect the register map used by `core/codec.py`.
- For Active-Send, confirm the field exists in the 11-register response payload.
- Verify whether the value needs signed decoding, decimal scaling, unit mapping, or status-bit decoding.

### Step 2 — Decode into `interpreted`

Add the field in the decode path so each `MeasurementFrame.interpreted` has a stable key.

Preferred field naming:

| Kind                             | Pattern                                        |
| -------------------------------- | ---------------------------------------------- |
| raw board integer                | `<name>_raw_value`                             |
| decimal-scaled engineering value | `<name>_value`                                 |
| canonical bridge alias           | `reference_<meaning>`                          |
| status/flags                     | `<name>_status`, `status_word`, `status_flags` |

### Step 3 — Register plot metadata if operator-selectable

If the field should appear in the UI signal dropdown, add it to `SIGNAL_DEFINITIONS` in `core/signals.py` with:

- `label`,
- `description`,
- `unit_hint`,
- `source`.

### Step 4 — Update logs and IPC only if needed

- Logs can already preserve all `interpreted` fields in `interpreted_signal.ndjson`.
- Add explicit CSV columns only if the field is operator-facing and stable.
- Add IPC fields only if `LSL_Bridge` or downstream tools need them.

### Step 5 — Add tests

Minimum tests:

```bash
uv run pytest tests/unit/test_codec.py
uv run pytest tests/unit/test_signals.py
uv run pytest tests/integration/test_active_send_parser.py
```

## How to add a UI control

### Step 1 — Decide whether the control is runtime-only or config-backed

| Control type                | Store in                                             |
| --------------------------- | ---------------------------------------------------- |
| Runtime-only operator state | `state.py` / `RuntimeSettings`                       |
| Persistent default          | `config/config.yaml` + `config/schema.py`            |
| Display behavior            | `ui` config section                                  |
| Acquisition behavior        | `device`, `serial`, or `active_send` config sections |

### Step 2 — Add UI element

Likely file:

```text
src/rs485_gui/ui/layout.py
```

### Step 3 — Update refresh behavior

Likely file:

```text
src/rs485_gui/ui/refresh.py
```

### Step 4 — Ensure worker safety

If the UI control affects acquisition, ensure the change is thread-safe. Avoid directly mutating transport internals from UI callbacks.

### Step 5 — Document and test

Update:

- `docs/configuration.md` if config-backed,
- `docs/workflow.md` if operator-facing,
- e2e/UI tests if present.

## How to add logger outputs

### Step 1 — Identify artifact class

| Artifact                           | File                        |
| ---------------------------------- | --------------------------- |
| raw wire/register audit            | `raw_signal.ndjson`         |
| decoded engineering values         | `interpreted_signal.ndjson` |
| spreadsheet-friendly stable values | `gui_signal.csv`            |
| operator/runtime events            | `event.log`                 |
| Python/module debug                | `acquisition_debug.log`     |

### Step 2 — Update `SignalFileLogger`

File:

```text
src/rs485_gui/io/logger.py
```

Rules:

- Keep writes serialized through the existing logger lock.
- Avoid expensive per-frame formatting at 500 Hz unless needed.
- If adding CSV columns, update the header and tests together.
- Preserve NDJSON as the audit-friendly flexible format.

### Step 3 — Update docs and tests

```bash
uv run pytest tests/integration/test_file_logger.py
```

Update:

- [RS485_GUI/docs/logging-and-outputs.md](logging-and-outputs.md),
- `docs/configuration.md` if new config keys are added.

## How to update IPC payloads

IPC fields are cross-component contracts.

Before changing `io/publisher.py`, check:

- [docs/architecture/stream-contracts.md](../../docs/architecture/stream-contracts.md),
- [LSL_Bridge/docs/stream-contracts.md](../../LSL_Bridge/docs/stream-contracts.md),
- `LSL_Bridge` IPC subscriber/parser expectations,
- calibration configs and docs that expect `reference_force_N`.

Required preserved fields for bridge compatibility:

- `schema`,
- `seq`,
- `session_id`,
- `mode`,
- `signal_key`,
- `reference_force_N`,
- `reference_clock_s`,
- `reference_status`,
- `board_profile`.

If changing any of these, update the bridge and root contract docs in the same commit.

## How to add config keys

1. Add the default in `RS485_GUI/config/config.yaml`.
2. Add the dataclass field in `src/rs485_gui/config/schema.py`.
3. Use the key through the loaded `cfg` object.
4. Add tests in `tests/unit/test_config.py`.
5. Document the key in `docs/configuration.md`.

Do not use `@hydra.main` in this app. The loader deliberately avoids Hydra global runtime initialization since this app is a simple CLI/script entry point, not a Hydra-managed run.

## Manual validation after development

After code tests pass, run a short hardware validation:

```bash
cd RS485_GUI
uv run rs485-gui serial.default_port=/dev/ttyUSB_RS485 app.log_level=INFO
```

Then verify:

- UI opens,
- board display and GUI signal agree qualitatively,
- `raw_signal.ndjson` and `interpreted_signal.ndjson` update,
- `gui_signal.csv` has expected header and values,
- IPC publisher binds when acquisition starts,
- `LSL_Bridge` can consume `rs485.measurement.v1`.

## Anti-regression checklist

- [ ] No acquisition logic moved into UI-only code.
- [ ] No parser/IPC contract changed without bridge docs/tests update.
- [ ] No file logger change breaks CSV header tests.
- [ ] No config key exists in YAML but not schema, or schema but not docs.
- [ ] No display limiter accidentally applied to IPC/logging path.
- [ ] No code path binds the ZMQ endpoint during NiceGUI construction unless intentionally reworked and tested.
