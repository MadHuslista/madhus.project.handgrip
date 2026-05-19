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

## Documentation map

| Document                                   | Purpose                                                                            |
| ------------------------------------------ | ---------------------------------------------------------------------------------- |
| [workflow.md](workflow.md)                 | Prerequisites, startup options, stream validation, output paths                    |
| [configuration.md](configuration.md)       | Full config reference: serial, IPC, streams, timestamping, CSV, processing filters |
| [stream-contracts.md](stream-contracts.md) | Stream names, channel labels, sample rates, event schema                           |
| [timestamping.md](timestamping.md)         | LSL clock offset, dejitter, interpolation, gap handling                            |
| [architecture.md](architecture.md)         | Core/io/publishers layers and runtime dataflow                                     |
| [development.md](development.md)           | How to add channels, parser fields, publishers, and tests                          |

## Reading guide

- To start the bridge and validate streams: [LSL_Bridge/docs/workflow.md](workflow.md)
- To edit serial or stream configuration: [LSL_Bridge/docs/configuration.md](configuration.md)
- To understand stream channel labels and contracts: [LSL_Bridge/docs/stream-contracts.md](stream-contracts.md)
- To understand timestamp handling: [LSL_Bridge/docs/timestamping.md](timestamping.md)
- To understand the codebase: [LSL_Bridge/docs/architecture.md](architecture.md)

## Related docs

- [docs/workflows/target-only-quickstart.md](../../docs/workflows/target-only-quickstart.md) — validate target chain without reference
- [docs/workflows/reference-only-quickstart.md](../../docs/workflows/reference-only-quickstart.md) — validate reference chain
- [docs/architecture/stream-contracts.md](../../docs/architecture/stream-contracts.md) — root cross-component stream contracts
- [docs/troubleshooting/lsl-streams.md](../../docs/troubleshooting/lsl-streams.md)
