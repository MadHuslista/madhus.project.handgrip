# LSL Bridge Documentation

## Summary

- `LSL_Bridge` publishes the canonical LSL streams `HandgripTarget` and `HandgripReference`.
- It ingests target serial `D2`/`M2` frames and RS485 GUI ZeroMQ IPC messages, timestamps them, and publishes synchronized LSL streams.
- Start after `RS485_GUI` is running (if the reference stream is needed) and after firmware is emitting `D2` frames.

## Component contract

| Contract          | Value                                                            |
| ----------------- | ---------------------------------------------------------------- |
| Primary command   | `uv run lsl-bridge`                                              |
| Main config       | `LSL_Bridge/conf/config.yaml`                                    |
| Published streams | `HandgripTarget`, `HandgripReference`, `HandgripComponentEvents` |
| IPC input         | `rs485.measurement.v1` from `RS485_GUI`                          |

## Reading guide

| I want to…                                             | Read                                                       |
| ------------------------------------------------------ | ---------------------------------------------------------- |
| Start the bridge and validate streams                  | [LSL_Bridge/docs/workflow.md](workflow.md)                 |
| Edit serial, IPC, or stream configuration              | [LSL_Bridge/docs/configuration.md](configuration.md)       |
| Understand stream names, channel labels, and contracts | [LSL_Bridge/docs/stream-contracts.md](stream-contracts.md) |
| Understand timestamp handling (offset, dejitter, gaps) | [LSL_Bridge/docs/timestamping.md](timestamping.md)         |
| Understand core/io/publishers internals                | [LSL_Bridge/docs/architecture.md](architecture.md)         |
| Add channels, parser fields, or publishers             | [LSL_Bridge/docs/development.md](development.md)           |

## Related docs

- [docs/workflows/target-only-quickstart.md](../../docs/workflows/target-only-quickstart.md) — validate target chain without reference
- [docs/workflows/reference-only-quickstart.md](../../docs/workflows/reference-only-quickstart.md) — validate reference chain
- [docs/architecture/stream-contracts.md](../../docs/architecture/stream-contracts.md) — root cross-component stream contracts
- [docs/troubleshooting/lsl-streams.md](../../docs/troubleshooting/lsl-streams.md)
