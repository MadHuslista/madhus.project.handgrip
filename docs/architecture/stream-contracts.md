# Stream and Data Contracts

## Summary

- This document is the **root source of truth** for cross-component stream, IPC, serial, and session data contracts in the Handgrip Suite.
- The current target firmware serial contract is `M2` metadata plus strict `D2` data frames.
- `LSL_Bridge` is the runtime boundary that converts firmware UART and RS485 GUI IPC into canonical Lab Streaming Layer (LSL) streams.
- `LSL_Viewer`, `Handgrip_Calibration`, and downstream recording/analysis workflows should depend on the contracts documented here instead of reverse-engineering source modules.
- If any stream name, channel label, serial field, IPC topic, or calibration-authoritative signal changes, update this document, the relevant component docs/configs, and tests together.

## Audience

Read this document if you need to:

- understand how live data moves between components,
- debug stream discovery or missing signals,
- change a stream name or channel name,
- add new target/reference channels,
- validate calibration inputs,
- maintain compatibility across firmware, bridge, viewer, calibration, and analysis modules.

## Status

| Field                       | Value                                                                                                                                                         |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Status                      | Canonical root architecture document                                                                                                                          |
| Scope                       | Cross-component stream, IPC, serial, and session contracts                                                                                                    |
| Component owner             | Root architecture docs; implemented primarily by `LSL_Bridge`                                                                                                 |
| Primary producer components | `Handgrip_Firmware`, `RS485_GUI`, `LSL_Bridge`, `Handgrip_Calibration`                                                                                        |
| Primary consumer components | `LSL_Viewer`, `Handgrip_Calibration`, recordings, analysis workflows                                                                                          |
| Related docs                | [`docs/architecture/dataflow.md`](dataflow.md), [`Handgrip_Firmware/docs/serial-protocol.md`](../../Handgrip_Firmware/docs/serial-protocol.md), [`LSL_Bridge/docs/stream-contracts.md`](../../LSL_Bridge/docs/stream-contracts.md), [`Handgrip_Calibration/docs/protocols.md`](../../Handgrip_Calibration/docs/protocols.md) |

---

## Minimum required contracts

This table is the minimum cross-component contract set required by the Phase 5 documentation plan.

| Stream / channel          | Source                          | Consumer            | Notes                                   |
| ------------------------- | ------------------------------- | ------------------- | --------------------------------------- |
| `HandgripTarget`          | `LSL_Bridge` from firmware UART | Viewer, calibration | D2 payload derived.                     |
| `HandgripReference`       | `LSL_Bridge` from RS485 GUI IPC | Viewer, calibration | Reference force from acquisition board. |
| `HandgripComponentEvents` | `LSL_Bridge`                    | Diagnostics         | Connect/disconnect/gap markers.         |
| `rs485.measurement.v1`    | `RS485_GUI`                     | `LSL_Bridge`        | ZMQ IPC topic.                          |

The detailed sections below are the authoritative expanded contract.

---

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

Handgrip_Calibration
  └─ calibration protocol marker events
      ↓
  LSL stream / session event artifacts: HandgripCalibrationMarkers / events.ndjson

LSL streams and session artifacts
  ├─ LSL_Viewer
  ├─ Handgrip_Calibration
  ├─ XDF / CSV recording workflows
  └─ Handgrip_Analysis / report workflows
```

---

## Firmware UART contract

The target firmware emits metadata and data lines over UART. `LSL_Bridge` parses these lines and publishes the target LSL stream.

### Metadata frame

```text
M2,<payload_schema>,<firmware_version>,<git_sha>,<expected_rate_hz>,<scale_factor>,<scale_offset>,<unit>
```

### Data frame

```text
D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>
```

### Field meanings

| Field           | Meaning                                                                               | Main consumer / behavior                                            |
| --------------- | ------------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| `seq`           | Monotonic sample sequence number.                                                     | `LSL_Bridge`, diagnostics, dropped-sample and reordering checks.    |
| `timestamp_us`  | Firmware device-local timestamp in microseconds, typically from `micros()`.           | `LSL_Bridge` timestamp anchoring and timing diagnostics.            |
| `raw_count`     | HX711 raw ADC count.                                                                  | Calibration-authoritative target signal and offline analysis input. |
| `current_units` | Firmware-scaled engineering/sanity value using currently deployed firmware constants. | Viewer/operator sanity checks and post-deployment validation.       |
| `status`        | Firmware acquisition/scaling status bitfield.                                         | QA, troubleshooting, and exclusion/flagging logic.                  |

The legacy `D,<seq>,<timestamp_us>,<value_gr>` format is **not** the current protocol and must not be used in canonical documentation or new parser logic.

### Parser expectation

The bridge-side D2 parser should remain strict. A malformed data line should be dropped/logged rather than guessed.

Valid examples:

```text
D2,0,123456,-842133,0.000000,0
D2,1,134002,-842129,nan,4
```

Invalid examples:

```text
D,1,134002,12.3
D2,42,,123456,-842133,12.3,0
D2,42,123456,-842133,12.3
```

Do not make the parser permissive unless all downstream consumers are deliberately migrated and the schema change is documented here.

---

## RS485 GUI IPC contract

`RS485_GUI` is the reference acquisition process. It reads the PM58/acquisition-board chain and publishes normalized reference measurements to `LSL_Bridge` over ZeroMQ.

| Item                                          | Canonical value                                         |
| --------------------------------------------- | ------------------------------------------------------- |
| Producer                                      | `RS485_GUI`                                             |
| Consumer                                      | `LSL_Bridge`                                            |
| Transport                                     | ZeroMQ PUB/SUB                                          |
| Topic                                         | `rs485.measurement.v1`                                  |
| Main semantic payload                         | Reference-force measurement from the acquisition board. |
| Acquisition modes hidden behind this contract | Vendor Active-Send mode or Modbus RTU polling.          |

The IPC payload should be treated as the normalized output of the reference acquisition process. Downstream components should not need to know whether the board was read through Active-Send or Modbus RTU polling.

The RS485 GUI IPC contract is not a substitute for LSL. It is an internal host-side bridge transport from the reference acquisition application to the LSL bridge.

---

## LSL stream contracts

### `HandgripTarget`

| Property                         | Expected value                                          |
| -------------------------------- | ------------------------------------------------------- |
| Producer                         | `LSL_Bridge` target serial reader                       |
| Upstream source                  | `Handgrip_Firmware` D2 UART lines                       |
| Sampling                         | Irregular / target-device paced                         |
| Primary calibration channel      | Raw ADC count / raw target value                        |
| Calibration-authoritative signal | `target_raw_count`                                      |
| Consumer examples                | `LSL_Viewer`, `Handgrip_Calibration`, XDF/CSV recording |

Recommended semantic channel contract:

| Semantic channel       | Source field    | Meaning                                                      |
| ---------------------- | --------------- | ------------------------------------------------------------ |
| `device_clock_us`      | `timestamp_us`  | Firmware device-local microsecond timestamp.                 |
| `target_raw_count`     | `raw_count`     | HX711 raw ADC count; calibration-authoritative target value. |
| `target_current_units` | `current_units` | Firmware-scaled diagnostic/operator value.                   |
| `target_status`        | `status`        | Firmware acquisition/scaling status bitfield.                |
| `target_sequence`      | `seq`           | Sample sequence number for gap/reordering diagnostics.       |

If the implementation channel order differs from this semantic table, keep the implementation docs and active config-specific channel map authoritative, but preserve these semantic names across documentation, session outputs, and downstream analysis.

### `HandgripReference`

| Property                         | Expected value                                                                           |
| -------------------------------- | ---------------------------------------------------------------------------------------- |
| Producer                         | `LSL_Bridge` reference IPC subscriber                                                    |
| Upstream source                  | `RS485_GUI` ZeroMQ publication from PM58/acquisition-board chain                         |
| Sampling                         | Nominally regular reference stream; recommended operating profile is 500 Hz Active-Send. |
| Primary calibration channel      | Physical reference force.                                                                |
| Calibration-authoritative signal | Reference force / net force channel in Newtons.                                          |
| Consumer examples                | `LSL_Viewer`, `Handgrip_Calibration`, XDF/CSV recording                                  |

Recommended semantic channel contract:

| Semantic channel                  | Meaning                                                     |
| --------------------------------- | ----------------------------------------------------------- |
| `reference_force_n` / `net_value` | Reference force value used as calibration ground truth.     |
| `reference_raw` / `raw_value`     | Board-native or raw measurement when available.             |
| `reference_status`                | Board/transport status when available.                      |
| `host_time` / metadata            | Host receive or publication timing metadata when available. |

The exact channel names and channel order should match the active `LSL_Bridge/conf/config.yaml`, `RS485_GUI/config/config.yaml`, and viewer/calibration configs. If a channel name changes, update all producer and consumer configs together.

### `HandgripComponentEvents`

| Property       | Expected value                                                                                                                               |
| -------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| Producer       | `LSL_Bridge`                                                                                                                                 |
| Purpose        | Operational diagnostics.                                                                                                                     |
| Event examples | Target metadata received, connect, disconnect, parser warning, target sequence gap, reference IPC gap, malformed payload, stream start/stop. |
| Consumers      | Operators, troubleshooting docs, optional recordings, calibration QA, future reports.                                                        |

### `HandgripCalibrationMarkers`

| Property  | Expected value                                                                                                                         |
| --------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| Producer  | `Handgrip_Calibration`                                                                                                                 |
| Purpose   | Calibration protocol events: baseline start/end, hold start/end, target force level, dynamic trial markers, holdout validation events. |
| Consumers | `LSL_Viewer`, calibration reports, XDF/session reconstruction.                                                                         |

`HandgripCalibrationMarkers` may appear as an LSL marker stream, as `events.ndjson`, or both depending on the capture mode and workflow. The exact runtime representation is component-owned, but the semantic role is system-level and should be preserved.

---

## Calibration contract

Calibration should fit target raw counts against reference force:

```text
reference_force_N = f(target_raw_count)
```

Do not fit primarily against `target_current_units` unless a workflow explicitly states that it is validating already-deployed firmware constants.

Minimum session inputs for fitting:

| Input                        | Required role                               |
| ---------------------------- | ------------------------------------------- |
| Target raw count time series | Model input.                                |
| Reference force time series  | Ground-truth output.                        |
| Protocol event markers       | Segment static holds and validation trials. |
| Firmware metadata            | Preserve schema/version/constants.          |
| Component config snapshots   | Reproducibility and debugging.              |

### Why raw counts are authoritative

`target_current_units` is useful for operator feedback, but it is already transformed by whatever firmware constants were deployed at capture time. Fitting against it can hide the true target calibration problem or accidentally validate stale firmware constants. The clean calibration path is:

```text
target_raw_count + reference_force_N + protocol events → fitted model/constants → deployment/validation
```

---

## Session output contracts

Calibration sessions should produce a folder under:

```text
Handgrip_Calibration/data/calibration/<session_id>/
```

Expected artifact classes:

| Artifact                                          | Purpose                                                                                           |
| ------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| `target.csv` or equivalent target data file       | Captured target stream samples. Exact filename is owned by `Handgrip_Calibration` docs/config.    |
| `reference.csv` or equivalent reference data file | Captured reference stream samples. Exact filename is owned by `Handgrip_Calibration` docs/config. |
| `events.ndjson`                                   | Protocol and marker events.                                                                       |
| `quality_live.ndjson` or equivalent QA log        | Live quality/diagnostic events when enabled.                                                      |
| config snapshots                                  | Reproducibility of component settings.                                                            |
| fit result JSON                                   | Selected calibration model and parameters.                                                        |
| candidate/model-selection JSON                    | Alternative model comparisons when enabled.                                                       |
| report Markdown/HTML                              | Human-readable result interpretation.                                                             |

Exact artifact names and optional outputs should be documented in [`Handgrip_Calibration/docs/reports-and-outputs.md`](../../Handgrip_Calibration/docs/reports-and-outputs.md) and [`Handgrip_Calibration/docs/recording.md`](../../Handgrip_Calibration/docs/recording.md). This root document defines artifact roles, not every implementation filename.

---

## Data ownership boundaries

| Contract area             | Owner                  | Root-level invariant                                                       |
| ------------------------- | ---------------------- | -------------------------------------------------------------------------- |
| Firmware serial schema    | `Handgrip_Firmware`    | Must emit current M2/D2 schema.                                            |
| Target LSL stream         | `LSL_Bridge`           | Must expose target raw count and timing metadata.                          |
| Reference acquisition IPC | `RS485_GUI`            | Must publish normalized reference measurements on `rs485.measurement.v1`.  |
| Reference LSL stream      | `LSL_Bridge`           | Must expose reference force suitable for calibration.                      |
| Calibration markers       | `Handgrip_Calibration` | Must preserve protocol boundaries/events for fitting and validation.       |
| Viewer rendering          | `LSL_Viewer`           | Must consume contracts; display settings must not redefine data semantics. |
| Analysis outputs          | `Handgrip_Analysis`    | Must document which captured/artifact fields are required.                 |

---

## Change-control rule

Changing a contract requires updating all of these at the same time:

1. producing code/config,
2. consuming code/config,
3. root architecture docs,
4. component docs,
5. parser/channel discovery tests or validation checklist,
6. example workflow docs.

Any change to these items is a cross-component migration:

- firmware frame prefix or field order,
- stream names,
- channel names or order,
- IPC topic name,
- reference force semantic field,
- calibration-authoritative target signal,
- session artifact names consumed by reports/analysis.

---

## Validation checklist

### Static documentation checks

```bash
# Confirm current D2 firmware schema is documented.
rg "D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>" \
  README.md docs Handgrip_Firmware LSL_Bridge

# Fail if canonical docs still mention the legacy target frame as current.
if rg "D,<seq>,<timestamp_us>,<value_gr>" README.md docs Handgrip_Firmware LSL_Bridge Handgrip_Calibration LSL_Viewer Handgrip_Analysis; then
  echo "ERROR: stale legacy firmware schema found in canonical docs" >&2
  exit 1
fi

# Confirm required stream/IPC contracts are documented.
rg "HandgripTarget|HandgripReference|HandgripComponentEvents|rs485.measurement.v1" \
  README.md docs LSL_Bridge LSL_Viewer Handgrip_Calibration

# Confirm calibration marker contract is preserved.
rg "HandgripCalibrationMarkers" README.md docs Handgrip_Calibration LSL_Viewer

# Check stale RS485 config snapshot path is gone.
if rg "\.\./RS485_GUI/config\.yaml|RS485_GUI/config\.yaml" Handgrip_Calibration/conf docs; then
  echo "ERROR: stale RS485 GUI config path found" >&2
  exit 1
fi

# Check canonical RS485 config path appears.
rg "RS485_GUI/config/config\.yaml" Handgrip_Calibration/conf docs
```

### Runtime validation checklist

1. Start target firmware serial output.
2. Confirm `M2` metadata appears at boot.
3. Confirm `D2` lines match `D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>`.
4. Start `RS485_GUI` and confirm reference measurements are live.
5. Start `LSL_Bridge` and confirm `HandgripTarget` appears.
6. Confirm `HandgripReference` appears after RS485 GUI IPC is active.
7. Confirm `HandgripComponentEvents` logs or stream events are produced when applicable.
8. Start `LSL_Viewer` and confirm target/reference traces are visible.
9. Run `handgrip-cal preflight --config conf/protocol_static_reversible_staircase_v3.yaml` and confirm both streams are resolved.
10. Run a short recording and verify target, reference, event, config-snapshot, and report artifacts are generated.

