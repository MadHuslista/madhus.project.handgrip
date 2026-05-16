# System Stream and Data Contracts

## Summary

- This document is the root-level source of truth for cross-component data contracts in the Handgrip Suite.
- The current target firmware serial contract is `M2` metadata plus strict `D2` data frames.
- `LSL_Bridge` is the boundary that converts firmware UART and RS485 GUI IPC into canonical Lab Streaming Layer streams.
- `Handgrip_Calibration`, `LSL_Viewer`, and `Handgrip_Analysis` should depend on the contracts documented here instead of reverse-engineering source modules.

## Audience

Read this document if you need to:

- understand how data moves between components,
- change a stream name or channel name,
- debug stream discovery,
- add new channels,
- validate calibration inputs,
- maintain cross-component compatibility.

## Status

| Field                  | Value                                                                                                                        |
| ---------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| Canonical              | Yes                                                                                                                          |
| Scope                  | Cross-component stream/data contracts                                                                                        |
| Component owner        | Root architecture docs; implemented primarily by `LSL_Bridge`                                                                |
| Related component docs | `Handgrip_Firmware/docs/serial-protocol.md`, `LSL_Bridge/docs/stream-contracts.md`, `Handgrip_Calibration/docs/protocols.md` |

## Contract map

```text
Arduino/HX711 target firmware
  └─ UART 115200 8N1
      ├─ M2 metadata line
      └─ D2 data lines
          ↓
LSL_Bridge target parser
  └─ LSL stream: HandgripTarget

PM58 + acquisition board
  └─ RS485 / USB-RS485
      ↓
RS485_GUI
  └─ ZeroMQ topic: rs485.measurement.v1
      ↓
LSL_Bridge reference IPC subscriber
  └─ LSL stream: HandgripReference

LSL streams
  ├─ LSL_Viewer
  ├─ Handgrip_Calibration
  └─ record/replay/analysis workflows
```

## Firmware UART contract

### Metadata frame

```text
M2,<payload_schema>,<firmware_version>,<git_sha>,<expected_rate_hz>,<scale_factor>,<scale_offset>,<unit>
```

### Data frame

```text
D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>
```

### Field meanings

| Field           | Meaning                           | Main consumer                                     |
| --------------- | --------------------------------- | ------------------------------------------------- |
| `seq`           | Monotonic sample sequence number  | `LSL_Bridge`, diagnostics, dropped-sample checks. |
| `timestamp_us`  | Device-local `micros()` timestamp | `LSL_Bridge` timestamping, timing diagnostics.    |
| `raw_count`     | HX711 raw ADC count               | Calibration fitting and analysis.                 |
| `current_units` | Firmware-scaled sanity value      | Viewer/operator sanity checks.                    |
| `status`        | Acquisition status bitfield       | QA and troubleshooting.                           |

The legacy `legacy D-prefix three-field value frame` format is not the current protocol.

## LSL stream contracts

### `HandgripTarget`

| Field                            | Value                                                   |
| -------------------------------- | ------------------------------------------------------- |
| Producer                         | `LSL_Bridge` target serial reader                       |
| Upstream source                  | `Handgrip_Firmware` D2 UART lines                       |
| Consumer examples                | `LSL_Viewer`, `Handgrip_Calibration`, XDF/CSV recording |
| Nominal rate                     | Irregular / device-dependent                            |
| Calibration-authoritative signal | `target_raw_count`                                      |

Recommended channel contract:

| Channel                | Meaning                       | Source field    |
| ---------------------- | ----------------------------- | --------------- |
| `device_clock_us`      | Firmware `micros()` timestamp | `timestamp_us`  |
| `target_raw_count`     | HX711 raw ADC count           | `raw_count`     |
| `target_current_units` | Firmware-scaled sanity value  | `current_units` |
| `target_status`        | Firmware status bitfield      | `status`        |
| `target_sequence`      | Monotonic sample sequence     | `seq`           |

If implementation order differs from this table, keep the implementation docs and config-specific channel map authoritative, but preserve these semantic names across docs and downstream outputs.

### `HandgripReference`

| Field                            | Value                                                   |
| -------------------------------- | ------------------------------------------------------- |
| Producer                         | `LSL_Bridge` reference IPC subscriber                   |
| Upstream source                  | `RS485_GUI` ZeroMQ publication from acquisition board   |
| Consumer examples                | `LSL_Viewer`, `Handgrip_Calibration`, XDF/CSV recording |
| Recommended operational rate     | 500 Hz reference stream when using Active-Send profile  |
| Calibration-authoritative signal | Reference force / net force channel in Newtons          |

Recommended semantic channel contract:

| Channel                           | Meaning                                                      |
| --------------------------------- | ------------------------------------------------------------ |
| `reference_force_n` / `net_value` | Reference force value used for calibration.                  |
| `reference_raw` / `raw_value`     | Raw or board-native measurement when available.              |
| `reference_status`                | Board/transport status when available.                       |
| `host_time` / metadata            | Host receive timing or publication metadata where available. |

The exact names should match the active `LSL_Bridge/conf/config.yaml`, `RS485_GUI/config/config.yaml`, and viewer/calibration configs. If a channel name changes, update all three components together.

### `HandgripComponentEvents`

| Field     | Value                                                                                                                   |
| --------- | ----------------------------------------------------------------------------------------------------------------------- |
| Producer  | `LSL_Bridge`                                                                                                            |
| Purpose   | Operational events such as metadata receipt, sequence gaps, parse errors, stream start/stop, and component diagnostics. |
| Consumers | Diagnostics, event logs, calibration QA, future reports.                                                                |

### `HandgripCalibrationMarkers`

| Field     | Value                                                                                                                                  |
| --------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| Producer  | `Handgrip_Calibration`                                                                                                                 |
| Purpose   | Calibration protocol events: baseline start/end, hold start/end, target force level, dynamic trial markers, holdout validation events. |
| Consumers | Viewer marker overlay, calibration reports, XDF/session reconstruction.                                                                |

## RS485 GUI IPC contract

| Field     | Value                                                               |
| --------- | ------------------------------------------------------------------- |
| Producer  | `RS485_GUI`                                                         |
| Consumer  | `LSL_Bridge`                                                        |
| Transport | ZeroMQ PUB/SUB                                                      |
| Topic     | `rs485.measurement.v1`                                              |
| Data role | Reference acquisition frames from the PM58/acquisition-board chain. |

The RS485 GUI IPC contract is not a substitute for LSL. It is an internal bridge transport from the reference acquisition application to the LSL bridge.

## Calibration contracts

Calibration should fit target raw counts against reference force:

```text
reference_force_N = f(target_raw_count)
```

Do not fit primarily against `target_current_units` unless a protocol explicitly states that it is validating already-deployed firmware constants.

Minimum session inputs for fitting:

| Input                        | Required role                               |
| ---------------------------- | ------------------------------------------- |
| Target raw count time series | Model input.                                |
| Reference force time series  | Ground-truth output.                        |
| Protocol event markers       | Segment static holds and validation trials. |
| Firmware metadata            | Preserve schema/version/constants.          |
| Component configs            | Reproducibility and debugging.              |

## Modification rules

Any change to stream names, channel names, frame schema, IPC topic, or calibration-authoritative signal is a cross-component change.

Update these together:

1. producing component config/source,
2. consuming component config/source,
3. root `docs/architecture/stream-contracts.md`,
4. component stream/config docs,
5. tests for parser/channel discovery,
6. example workflow docs.

## Validation commands

```bash
# Check legacy firmware schema is gone from canonical docs.
rg "D,<seq>|legacy engineering-value field" README.md docs Handgrip_Firmware LSL_Bridge Handgrip_Calibration LSL_Viewer Handgrip_Analysis || true

# Check current D2 schema is documented.
rg "D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>" README.md docs Handgrip_Firmware LSL_Bridge

# Check stale RS485 config snapshot path is gone.
rg "\.\./RS485_GUI/config\.yaml|RS485_GUI/config\.yaml" Handgrip_Calibration/conf docs || true

# Check canonical RS485 config path appears.
rg "RS485_GUI/config/config\.yaml" Handgrip_Calibration/conf docs
```
