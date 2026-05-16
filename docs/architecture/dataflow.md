# Handgrip Suite Dataflow

**Status:** Canonical root architecture document  
**Audience:** Operators, maintainers, and developers  
**Scope:** Physical-force-to-software-data path across firmware, RS485 acquisition, LSL, viewer, calibration, and analysis  
**Related docs:** [`docs/system-overview.md`](../system-overview.md), [`docs/architecture/stream-contracts.md`](stream-contracts.md), [`docs/workflows/full-live-viewer-quickstart.md`](../workflows/full-live-viewer-quickstart.md)

## Summary

- The Handgrip Suite has two acquisition paths: the **target path** from the Arduino/HX711 handgrip firmware, and the **reference path** from the PM58 load cell through the RS485 acquisition board.
- `RS485_GUI` owns reference-board acquisition and publishes reference measurements over ZeroMQ IPC.
- `LSL_Bridge` owns canonical Lab Streaming Layer (LSL) stream publication for both target and reference data.
- `LSL_Viewer`, `Handgrip_Calibration`, and `Handgrip_Analysis` are downstream consumers; they should not directly reinterpret low-level hardware protocols unless explicitly designed to do so.
- The most important data contract is that the firmware emits `D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>` and the bridge converts that into the `HandgripTarget` LSL stream.

## Dataflow at a glance

```text
Physical force applied to handgrip fixture
│
├── Target chain
│   ├── Handgrip load cell / strain-gauge bridge
│   ├── HX711 ADC
│   ├── Arduino Nano firmware
│   ├── USB UART serial frames: M2 metadata + D2 samples
│   └── LSL_Bridge target serial reader
│       └── LSL stream: HandgripTarget
│
└── Reference chain
    ├── PM58 reference load cell
    ├── High-speed acquisition instrument / board
    ├── RS485 physical link through USB-RS485 adapter
    ├── RS485_GUI acquisition process
    ├── ZeroMQ IPC topic: rs485.measurement.v1
    └── LSL_Bridge reference IPC subscriber
        └── LSL stream: HandgripReference

HandgripTarget + HandgripReference + events
│
├── LSL_Viewer: live plots, XY correlation, replay visualization
├── Handgrip_Calibration: preflight, record, fit, report, validate holdout
└── Handgrip_Analysis: offline analysis stages and filter design
```

## Ownership boundaries

| Boundary                   | Producer               | Consumer                           | Contract                                                     |
| -------------------------- | ---------------------- | ---------------------------------- | ------------------------------------------------------------ |
| Firmware UART              | `Handgrip_Firmware`    | `LSL_Bridge`                       | `M2` metadata and `D2` sample lines.                         |
| RS485 board link           | acquisition board      | `RS485_GUI`                        | Active-Send or Modbus RTU measurement frames.                |
| Reference IPC              | `RS485_GUI`            | `LSL_Bridge`                       | ZMQ topic `rs485.measurement.v1`.                            |
| LSL streams                | `LSL_Bridge`           | Viewer/calibration/recording tools | Stream names, channel labels, timestamps, nominal rates.     |
| Calibration session folder | `Handgrip_Calibration` | Reports, users, analysis tools     | `target.csv`, `reference.csv`, event logs, fit/report files. |
| Analysis output folder     | `Handgrip_Analysis`    | Users and maintainers              | Stage reports, plots, metrics, filter recommendation files.  |

## Target chain details

### Physical source

The target chain is the handgrip device under calibration. Its output is treated as the signal that must be mapped to physical force.

### Firmware source of truth

The firmware should emit:

```text
M2,<payload_schema>,<firmware_version>,<git_sha>,<expected_rate_hz>,<scale_factor>,<scale_offset>,<unit>
D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>
```

The `raw_count` field is the calibration-authoritative value. `current_units` is useful for operator feedback but should not be treated as the primary fit target unless the calibration workflow explicitly says so.

### Bridge transformation

`LSL_Bridge` parses the D2 line and publishes `HandgripTarget`. It should preserve enough metadata to diagnose dropped samples, invalid scale conversion, timestamp gaps, and parser failures.

## Reference chain details

### Physical source

The reference chain is PM58 load cell → acquisition board. It should be mechanically in the same force path as the target handgrip during calibration.

### Acquisition path

The board can be read by `RS485_GUI` through:

- **Active-Send mode** for high-rate push measurements.
- **Modbus RTU polling** as the documented fallback path.

For calibration, the preferred reference profile is high-rate, low-hidden-filtering acquisition. If Active-Send parsing is unstable, fall back to Modbus RTU polling.

### IPC transformation

`RS485_GUI` publishes normalized measurement events to `LSL_Bridge` over ZeroMQ. The bridge should be the only component that translates that IPC stream into the canonical `HandgripReference` LSL stream.

## Downstream consumers

| Consumer               | Inputs                                                               | Outputs                                  | Main use                                           |
| ---------------------- | -------------------------------------------------------------------- | ---------------------------------------- | -------------------------------------------------- |
| `LSL_Viewer`           | `HandgripTarget`, `HandgripReference`, optional marker/event streams | Browser visualization                    | Validate live signals and timing behavior.         |
| `Handgrip_Calibration` | target/reference LSL streams and markers                             | Calibration session folder + reports     | Fit target raw counts to reference force.          |
| `Handgrip_Analysis`    | CSV/session/manifest inputs                                          | Stage reports and filter recommendations | Offline signal characterization and DSP decisions. |

## Validation checklist

- [ ] Firmware serial monitor shows `M2` followed by `D2` lines.
- [ ] `RS485_GUI` shows live reference force and publishes IPC events.
- [ ] `LSL_Bridge` reports both `HandgripTarget` and `HandgripReference` outlets.
- [ ] `LSL_Viewer` shows target and reference time series.
- [ ] Calibration preflight discovers both streams.
- [ ] Calibration recording produces target/reference CSVs.
- [ ] Analysis workflow can consume expected inputs from session or manifest files.
