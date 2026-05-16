# LSL Bridge Stream Contracts

## Summary

- `LSL_Bridge` owns the runtime conversion from target UART and reference IPC data into Lab Streaming Layer streams.
- The target side consumes current firmware `M2` / `D2` frames.
- The reference side consumes `RS485_GUI` ZeroMQ messages on `rs485.measurement.v1`.
- This component doc explains the bridge-specific implementation contract. The root contract is `docs/architecture/stream-contracts.md`.

## Audience

Read this document if you need to:

- run or debug `LSL_Bridge`,
- verify target/reference stream schemas,
- extend bridge channel output,
- update parser behavior,
- understand what calibration and viewer modules expect from the bridge.

## Status

| Field                | Value                                       |
| -------------------- | ------------------------------------------- |
| Canonical            | Yes                                         |
| Component            | `LSL_Bridge`                                |
| Related root doc     | `docs/architecture/stream-contracts.md`     |
| Related firmware doc | `Handgrip_Firmware/docs/serial-protocol.md` |

## Inputs

### Target UART input

`LSL_Bridge` reads the target handgrip firmware over serial.

Current data frame:

```text
D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>
```

Current metadata frame:

```text
M2,<payload_schema>,<firmware_version>,<git_sha>,<expected_rate_hz>,<scale_factor>,<scale_offset>,<unit>
```

The bridge parser is strict by design. A malformed data line is dropped and logged instead of being guessed.

### Reference IPC input

`LSL_Bridge` subscribes to the RS485 GUI ZeroMQ publication.

| Field    | Value                                                               |
| -------- | ------------------------------------------------------------------- |
| Producer | `RS485_GUI`                                                         |
| Topic    | `rs485.measurement.v1`                                              |
| Purpose  | Reference force measurements from the PM58/acquisition-board chain. |

## Outputs

### `HandgripTarget`

| Field          | Value                                            |
| -------------- | ------------------------------------------------ |
| Producer       | `LSL_Bridge`                                     |
| Source         | Firmware D2 frames                               |
| Rate           | Irregular / target-timed                         |
| Main consumers | `LSL_Viewer`, `Handgrip_Calibration`, recordings |

Semantic channels:

| Semantic name          | Source field    | Meaning                                         |
| ---------------------- | --------------- | ----------------------------------------------- |
| `device_clock_us`      | `timestamp_us`  | Device-local microsecond timestamp.             |
| `target_raw_count`     | `raw_count`     | HX711 raw ADC count; calibration-authoritative. |
| `target_current_units` | `current_units` | Firmware-scaled sanity value.                   |
| `target_status`        | `status`        | Firmware acquisition bitfield.                  |
| `target_sequence`      | `seq`           | Sample sequence number.                         |

### `HandgripReference`

| Field            | Value                                                        |
| ---------------- | ------------------------------------------------------------ |
| Producer         | `LSL_Bridge`                                                 |
| Source           | RS485 GUI IPC measurement frames                             |
| Recommended rate | 500 Hz when the acquisition board uses Active-Send at 500 Hz |
| Main consumers   | `LSL_Viewer`, `Handgrip_Calibration`, recordings             |

Semantic channels depend on the active RS485 GUI and bridge configuration. Keep the reference force/net-force channel stable across viewer and calibration configs.

### `HandgripComponentEvents`

This event stream is used for operational diagnostics.

Typical event classes:

- target metadata received,
- target sequence gap,
- parse warning,
- reference IPC gap or malformed payload,
- stream start/stop,
- component state transitions.

## Parser behavior

The D2 parser expects:

```text
D2,<digits>,<digits>,<number>,<number>,<digits>
```

Valid examples:

```text
D2,0,123456,-842133,0.000000,0
D2,1,134002,-842129,nan,4
```

Invalid examples:

```text
legacy D-prefix three-field value frame
D2,42,,123456,-842133,12.3,0
D2,42,123456,-842133,12.3
```

Invalid target lines should trigger bridge logs. Do not “fix” this by making the parser permissive unless all downstream consumers are deliberately migrated.

## Calibration implications

For calibration, the bridge must preserve:

- `target_raw_count`,
- target sample sequence,
- target device timestamp,
- reference force value,
- host/LSL timestamps,
- component metadata and configs.

The calibration model should primarily use `target_raw_count` as the target-device input and reference force as ground truth.

## When changing stream channels

Changing a channel is a cross-component migration. Update together:

1. `LSL_Bridge/conf/config.yaml`,
2. bridge outlet/type code,
3. parser tests,
4. `LSL_Viewer/conf/config.yaml`,
5. `Handgrip_Calibration/conf/*.yaml`,
6. root stream contracts,
7. this component doc.

## Validation checklist

```bash
uv run pytest LSL_Bridge/tests/unit/test_parser.py
uv run pytest LSL_Bridge/tests/unit/test_timestamping.py
uv run pytest LSL_Bridge/tests/integration/test_csv_sinks.py
```

Manual validation:

1. Start firmware serial output.
2. Start `LSL_Bridge`.
3. Confirm `M2` metadata is logged.
4. Confirm `HandgripTarget` appears in an LSL browser/viewer.
5. Start `RS485_GUI`.
6. Confirm `HandgripReference` appears.
7. Confirm `Handgrip_Calibration preflight` resolves both streams.
