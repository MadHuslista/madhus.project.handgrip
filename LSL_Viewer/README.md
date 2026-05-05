# LSL_Viewer — Calibration Schema v2

This viewer is aligned with the upgraded Handgrip stream schemas. It subscribes to the two native streams only:

- `HandgripTarget`: `seq`, `device_clock_us`, `target_raw_count`, `target_current_units`, `target_filtered_units`, `target_status`
- `HandgripReference`: `seq`, `reference_clock_s`, `reference_force_N`, `reference_status`

The viewer remains a visualization/debugging tool. It does not own calibration sessions, markers, fits, or reports; those are owned by `Handgrip_Calibration`. Optional marker overlays can be loaded from a calibration session `events.ndjson` for replay/inspection.
