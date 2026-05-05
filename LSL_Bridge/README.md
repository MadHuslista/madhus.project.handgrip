# LSL_Bridge — Calibration Schema v2

This bridge is a breaking upgrade. It accepts only the firmware `D2` payload and publishes the canonical LSL streams expected by `Handgrip_Calibration`.

## Streams

### `HandgripTarget`

Channels:

1. `seq`
2. `device_clock_us`
3. `target_raw_count`
4. `target_current_units`
5. `target_filtered_units`
6. `target_status`

### `HandgripReference`

Channels:

1. `seq`
2. `reference_clock_s`
3. `reference_force_N`
4. `reference_status`

### `HandgripComponentEvents`

Operational JSON marker stream. Calibration-trial markers are still owned by the `Handgrip_Calibration` module.
