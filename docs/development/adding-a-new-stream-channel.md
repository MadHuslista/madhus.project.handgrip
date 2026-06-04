# Adding a New Stream Channel

## Summary

- Adding a stream channel is a cross-component migration, not a local edit.
- Decide whether the channel belongs to `HandgripTarget`, `HandgripReference`, `HandgripComponentEvents`, or a new stream.
- Preserve calibration-authoritative signals: `target_raw_count` and reference force must remain stable.
- Update code, config, docs, tests, and workflows together.

## Files to edit

### Target channel from firmware D2

| File                                                                                           | Why                                                       |
| ---------------------------------------------------------------------------------------------- | --------------------------------------------------------- |
| `Handgrip_Firmware/Core/Src/main.cpp`                                                          | Emit the new field if firmware payload changes.           |
| `Handgrip_Firmware/Core/Inc/config.h`                                                          | Update schema metadata, comments, constants.              |
| [Handgrip_Firmware/docs/serial-protocol.md](../../Handgrip_Firmware/docs/serial-protocol.md) | Document the D2 schema change.                            |
| `LSL_Bridge/src/lsl_bridge/core/parser.py`                                                     | Parse the new field strictly.                             |
| `LSL_Bridge/conf/config.yaml`                                                                  | Add channel name/metadata.                                |
| [LSL_Bridge/docs/stream-contracts.md](../../LSL_Bridge/docs/stream-contracts.md)             | Document component-level stream schema.                   |
| [docs/architecture/stream-contracts.md](../architecture/stream-contracts.md)                 | Document root cross-component contract.                   |
| `LSL_Viewer/conf/config.yaml`                                                                  | Add viewer label if displayed.                            |
| `Handgrip_Calibration/conf/*.yaml`                                                             | Add or explicitly ignore channel if calibration needs it. |

### Reference channel from RS485 GUI IPC

| File                                                                 | Why                             |
| -------------------------------------------------------------------- | ------------------------------- |
| `RS485_GUI/src/rs485_gui/io/publisher.py`                            | Publish the new IPC field.      |
| [RS485_GUI/docs/ipc-schema.md](../../RS485_GUI/docs/ipc-schema.md) | Document topic/payload alias.   |
| `LSL_Bridge/src/lsl_bridge/publishers/reference.py`                  | Decode the new field.           |
| `LSL_Bridge/conf/config.yaml`                                        | Add reference stream channel.   |
| `LSL_Viewer/conf/config.yaml`                                        | Display/label if needed.        |
| `Handgrip_Calibration/conf/*.yaml`                                   | Use for recording/QA if needed. |

## Data contracts affected

Potentially affected contracts:

- `D2` firmware frame,
- `M2` metadata schema/version,
- `rs485.measurement.v1` IPC payload,
- `HandgripTarget` channel schema,
- `HandgripReference` channel schema,
- CSV/XDF recording columns,
- calibration session expected columns,
- analysis manifest expected columns.

Do not change channel order or names silently.

## Tests to update

Minimum test set depends on channel owner.

Target channel:

```bash
cd LSL_Bridge
uv run pytest tests/unit/test_parser.py
uv run pytest tests/integration/test_csv_sinks.py
```

Reference channel:

```bash
cd RS485_GUI
uv run pytest tests/integration/test_active_send_parser.py
uv run pytest tests/integration/test_file_logger.py

cd ../LSL_Bridge
uv run pytest tests/integration/test_csv_sinks.py
```

Viewer/calibration affected:

```bash
cd LSL_Viewer
uv run pytest

cd ../Handgrip_Calibration
uv run pytest
```

## Validation workflow

1. Update source/config/docs together.
2. Run parser/unit tests.
3. Start producer component.
4. Start `LSL_Bridge` and confirm stream appears.
5. Start `LSL_Viewer` and confirm label/plot behavior.
6. Run `handgrip-cal preflight`.
7. Record a short session and confirm new column is saved or intentionally excluded.
8. Update analysis manifests if analysis consumes the channel.

## Common failure modes

| Failure                                   | Cause                                          | Fix                                                        |
| ----------------------------------------- | ---------------------------------------------- | ---------------------------------------------------------- |
| Bridge drops all target lines             | D2 parser not updated for firmware field count | Update parser and tests.                                   |
| Viewer shows missing channel              | Viewer config label not updated                | Update `LSL_Viewer/conf/config.yaml` and docs.             |
| Calibration preflight fails               | Protocol expected old channel set              | Update calibration config or declare channel optional.     |
| CSV column order differs from docs        | CSV sink not updated                           | Update sink tests and output docs.                         |
| Analysis manifest fails                   | New channel absent from manifest               | Update manifest schema/docs.                               |
| Calibration semantics change accidentally | New field replaces raw count                   | Preserve `target_raw_count` and reference force contracts. |
