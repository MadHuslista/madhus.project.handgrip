# LSL Bridge Documentation

## Summary

- `LSL_Bridge` is the runtime boundary that publishes the Handgrip Suite's canonical Lab Streaming Layer (LSL) streams.
- It consumes the target firmware UART protocol (`M2` metadata and `D2` data lines) and the RS485 GUI ZeroMQ IPC topic (`rs485.measurement.v1`).
- It publishes `HandgripTarget`, `HandgripReference`, and `HandgripComponentEvents`.
- This component documentation explains how to run the bridge, configure streams, preserve timestamp semantics, extend channels safely, and validate parser/CSV behavior.

## Audience

| Reader                | Use this page to...                                                                           |
| --------------------- | --------------------------------------------------------------------------------------------- |
| Operator              | Start the bridge and confirm the expected LSL streams.                                        |
| Maintainer            | Find stream, timestamping, CSV, logging, and processing configuration references.             |
| Student developer     | Learn where parser, publisher, timestamp, outlet, and CSV behavior lives before editing code. |
| External collaborator | Understand how target serial and RS485 IPC become canonical LSL streams.                      |

## Component contract

`LSL_Bridge` owns the conversion from hardware-facing transports into canonical LSL streams.

```text
Handgrip_Firmware UART D2/M2  ─┐
                               ├─> LSL_Bridge ──> HandgripTarget
RS485_GUI rs485.measurement.v1 ─┘                  HandgripReference
                                                   HandgripComponentEvents
```

Downstream tools should consume the bridge outputs instead of reading firmware serial or RS485 IPC directly.

## Documentation map

| Document                                     | Purpose                                                                                                        |
| -------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| [`quickstart.md`](quickstart.md)             | Start bridge, override serial port, confirm target/reference/event streams.                                    |
| [`configuration.md`](configuration.md)       | Full `conf/config.yaml` reference, including streams, serial, IPC, timestamping, CSV, processing, and logging. |
| [`stream-contracts.md`](stream-contracts.md) | Component-specific target/reference/event stream schemas.                                                      |
| [`timestamping.md`](timestamping.md)         | Host receive vs device-clock anchor policy, drift guard, gap handling, and CSV/LSL timestamp meaning.          |
| [`architecture.md`](architecture.md)         | Serial input, IPC input, LSL outlets, CSV sinks, processing pipeline, and event flow.                          |
| [`development.md`](development.md)           | How to add channels, change parser behavior, or add processing stages safely.                                  |

## Related root docs

| Root doc                                                                                                                     | Why it matters                                    |
| ---------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------- |
| [`../../docs/architecture/stream-contracts.md`](../../docs/architecture/stream-contracts.md)                                 | Root cross-component stream and IPC contract.     |
| [`../../docs/architecture/dataflow.md`](../../docs/architecture/dataflow.md)                                                 | End-to-end target/reference dataflow.             |
| [`../../docs/architecture/runtime-processes.md`](../../docs/architecture/runtime-processes.md)                               | Start order and process ownership.                |
| [`../../docs/architecture/timestamping-and-synchronization.md`](../../docs/architecture/timestamping-and-synchronization.md) | System-level timing model.                        |
| [`../../docs/workflows/target-only-quickstart.md`](../../docs/workflows/target-only-quickstart.md)                           | Validate target firmware path through the bridge. |
| [`../../docs/workflows/full-live-viewer-quickstart.md`](../../docs/workflows/full-live-viewer-quickstart.md)                 | Run RS485 GUI, bridge, and viewer together.       |

## Related component docs

| Component doc                                                                                        | Why it matters                                          |
| ---------------------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| [`../../Handgrip_Firmware/docs/serial-protocol.md`](../../Handgrip_Firmware/docs/serial-protocol.md) | Target UART `M2`/`D2` contract consumed by the bridge.  |
| [`../../RS485_GUI/docs/ipc-schema.md`](../../RS485_GUI/docs/ipc-schema.md)                           | Reference IPC topic and payload produced by RS485 GUI.  |
| [`../../LSL_Viewer/docs/index.md`](../../LSL_Viewer/docs/index.md)                                   | Main consumer for live stream visualization.            |
| [`../../Handgrip_Calibration/docs/protocols.md`](../../Handgrip_Calibration/docs/protocols.md)       | Main consumer for target/reference calibration streams. |

## First operational path

1. Confirm target firmware emits D2 frames.
2. Start `RS485_GUI` if the reference stream is needed.
3. Start `LSL_Bridge` with the correct target serial port.
4. Confirm `HandgripTarget`, `HandgripReference`, and `HandgripComponentEvents` appear as expected.
5. Start `LSL_Viewer` or run `handgrip-cal preflight`.

## Validation checklist

- [ ] `quickstart.md` can start the bridge with explicit `serial.port=...`.
- [ ] `configuration.md` explains every top-level `conf/config.yaml` section.
- [ ] `stream-contracts.md` preserves target/reference/event stream schemas.
- [ ] `timestamping.md` explains `host_receive` and `device_clock_anchor` policies.
- [ ] `architecture.md` maps source modules to runtime responsibilities.
- [ ] `development.md` explains safe extension steps and tests.
