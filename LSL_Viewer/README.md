# Handgrip Real-Time Viewer

## Purpose

This viewer supports four explicit modes for the current handgrip pipeline:

- `live` — Connect to the live LSL stream for real-time monitoring
- `live_with_reference_validation` — Monitor live while validating against persisted CSV/XDF artifacts
- `csv_replay` — Replay a bridge CSV file for offline inspection
- `xdf_replay` — Replay a LabRecorder XDF file for offline inspection

It is designed around the current bridge contract:

1. `device_clock_us`
2. `grip_force_raw`
3. `grip_force_filtered`

The UI shows three panels:

- **raw signal** — the unfiltered device output
- **filtered signal** — the DSP-processed output
- **device sample interval** in milliseconds — computed from `device_clock_us` to expose timing irregularity

---

## Data-flow architecture

### 1. Live acquisition path

```text
Arduino
  -> serial frames
LSL_Bridge
  -> parse raw sample
  -> run DSP/filter pipeline
  -> publish LSL stream [device_clock_us, grip_force_raw, grip_force_filtered]
  -> write CSV in parallel
LabRecorder (optional)
  -> subscribe to the same LSL stream
  -> write XDF
Viewer (live modes)
  -> subscribe to the live LSL stream
  -> render rolling plots
```

### 2. Offline replay path

```text
CSV or XDF recording
  -> viewer replay loader
  -> replay timeline generator
  -> render the same rolling plots without a live LSL source
```

The important separation is:

- **live modes** read from the **LSL stream**
- **replay modes** read from **CSV or XDF files**
- reference files are no longer ambiguous because the mode determines whether they are the primary source or only a validation side input

---

## Modes

### `mode=live`

**Primary source:** live LSL stream

**Behavior:**
- Connects to the configured LSL stream
- Validates that the expected channels are present
- Plots the latest rolling window
- Ignores reference files as data sources

**Use this for:**
- Normal live monitoring during acquisition
- Watching the signal in real time as the device acquires data

**Environment requirements:**
- Bridge must be running and streaming on the network
- `mne-lsl` must be installed

### `mode=live_with_reference_validation`

**Primary source:** live LSL stream

**Side inputs:** optional CSV reference, optional XDF reference

**Behavior:**
- Loads and inspects the configured reference files first
- Connects to the live LSL stream
- Keeps plotting the live stream
- Uses the reference files only for schema/metadata validation and debugging context

**Use this for:**
- Checking that the live stream, bridge CSV, and recorded XDF are aligned
- Validating the integration after any bridge schema change
- Ensuring the recorder is capturing the same data the live stream shows

**Environment requirements:**
- Bridge must be running
- Reference files should be from the same acquisition session

### `mode=csv_replay`

**Primary source:** `reference.csv_path`

**Behavior:**
- Loads the bridge CSV
- Derives a replay timeline from the configured time column
- Replays the file at the configured speed
- Uses the same viewer layout as live mode

**Use this for:**
- Offline debugging of the bridge output
- Quick review of a previous session without starting LSL_Bridge or LabRecorder
- Checking filter behavior and signal quality post-acquisition

**Environment requirements:**
- CSV file must exist and be readable
- Python environment only (no network needed)

### `mode=xdf_replay`

**Primary source:** `reference.xdf_path`

**Behavior:**
- Loads the XDF with `pyxdf`
- Selects the stream that matches `stream.name`, `stream.stype`, and optionally `stream.source_id`
- Replays the recorded samples using their recorded timestamps
- Uses the same viewer layout as live mode

**Use this for:**
- Offline review of what LabRecorder captured
- Checking whether the recorder output matches expectations
- Verifying recorder fidelity and stream selection

**Environment requirements:**
- `pyxdf` must be installed for this mode
- XDF file must exist and be readable

---

## Expected stream / recording schema

The viewer assumes three numeric channels with these semantic roles:

- `device_clock_us` — the device-side sample timestamp in microseconds
- `grip_force_raw` — the unfiltered ADC or bridge-stage output
- `grip_force_filtered` — the DSP-processed output

For the **live LSL stream**, the channel labels must match the values in `channels.*`.

For **replay sources:**
- CSV columns are resolved by configured names first, then by fallback names such as `value_raw` and `value_filtered`
- XDF channels are resolved by labels stored in the stream metadata

---

## Installation

Typical dependencies:

- Python 3.10+
- `hydra-core`
- `numpy`
- `pandas`
- `matplotlib`
- `mne-lsl` for live modes
- `pyxdf` for XDF replay mode

Example with `uv`:

```bash
uv sync
uv run python handgrip_realtime_viewer.py
```

---

## Quick usage

### Live monitoring

```bash
uv run python handgrip_realtime_viewer.py mode=live
```

### Live monitoring with CSV/XDF validation

```bash
uv run python handgrip_realtime_viewer.py   mode=live_with_reference_validation   reference.csv_path=./data/handgrip_samples.csv   reference.xdf_path=./data/session01.xdf
```

### CSV replay

```bash
uv run python handgrip_realtime_viewer.py   mode=csv_replay   reference.csv_path=./data/handgrip_samples.csv
```

### XDF replay

```bash
uv run python handgrip_realtime_viewer.py   mode=xdf_replay   reference.xdf_path=./data/session01.xdf
```

### Faster replay

```bash
uv run python handgrip_realtime_viewer.py   mode=csv_replay   reference.csv_path=./data/handgrip_samples.csv   replay.speed=4.0
```

### Looping replay

```bash
uv run python handgrip_realtime_viewer.py   mode=xdf_replay   reference.xdf_path=./data/session01.xdf   replay.loop=true
```

---

## Configuration reference

## `mode`

- **Type:** string
- **Allowed values:** `live`, `live_with_reference_validation`, `csv_replay`, `xdf_replay`
- **Default:** `live`
- **Meaning:** Selects the primary data source and behavior of the viewer.

---

## `stream`

### `stream.name`
- **Type:** string
- **Default:** `ArduinoHandgrip`
- **Meaning:** LSL stream name used to resolve/connect to the correct stream.
- **Typical values:** any non-empty string
- **Recommended range:** exact producer stream name
- **Used by:** live modes, XDF replay stream selection
- **Notes:** If multiple streams share the same name, use `stream.source_id` as well.

### `stream.stype`
- **Type:** string
- **Default:** `Force`
- **Meaning:** LSL stream type filter.
- **Typical values:** `Force`, `EEG`, `Markers`, etc., but for this project it should normally stay `Force`.
- **Recommended range:** exact producer stream type
- **Used by:** live modes, XDF replay stream selection
- **Notes:** Must match the bridge metadata.

### `stream.source_id`
- **Type:** string or `null`
- **Default:** `null`
- **Meaning:** Optional unique identifier for one exact LSL source.
- **Typical values:** `null` or a stable unique string
- **Recommended range:** `null` if only one matching stream exists; otherwise set it explicitly.
- **Used by:** live modes, XDF replay stream selection
- **Notes:** Use this when multiple streams with the same `name` and `stype` are present.

### `stream.buffer_samples`
- **Type:** integer
- **Default:** `1600`
- **Meaning:** Ring buffer size used by the LSL client.
- **Valid range:** integer `>= 2`
- **Practical range:** roughly `2x` to `5x` the visible window length in samples
- **Used by:** live modes only
- **Guideline:** For an ~80 Hz stream, `1600` samples is about 20 seconds of storage.
- **Too low:** old data gets overwritten sooner, increased risk of losing context.
- **Too high:** more memory use and slightly more sluggish behavior when debugging.

### `stream.acquisition_delay`
- **Type:** float, seconds
- **Default:** `0.01`
- **Meaning:** Background acquisition polling interval for `mne-lsl`.
- **Valid range:** `> 0`
- **Practical range:** `0.001` to `0.05`
- **Used by:** live modes only
- **Lower values:** lower latency, more CPU wakeups.
- **Higher values:** less CPU overhead, slightly less responsive updates.
- **Recommendation:** keep near `0.005` to `0.02` unless you have a reason to tune it.

### `stream.timeout`
- **Type:** float, seconds
- **Default:** `5.0`
- **Meaning:** Timeout for initial LSL connection.
- **Valid range:** `> 0`
- **Practical range:** `1.0` to `30.0`
- **Used by:** live modes only
- **Lower values:** fail fast if the stream is absent.
- **Higher values:** more tolerant to slow discovery or slow startup.

---

## `channels`

These must match the bridge metadata for live mode, and they are also used to resolve replay channels.

### `channels.clock_label`
- **Type:** string
- **Default:** `device_clock_us`
- **Meaning:** Semantic label for the device clock channel.

### `channels.raw_label`
- **Type:** string
- **Default:** `grip_force_raw`
- **Meaning:** Semantic label for the raw signal channel.

### `channels.filtered_label`
- **Type:** string
- **Default:** `grip_force_filtered`
- **Meaning:** Semantic label for the filtered signal channel.

---

## `viewer`

### `viewer.window_samples`
- **Type:** integer or `null`
- **Default:** `null`
- **Meaning:** Explicit number of latest samples to display.
- **Valid range:** integer `>= 2` or `null`
- **Priority:** if set, it overrides `viewer.window_seconds`
- **Use when:** you want exact control over how many samples are plotted.

Examples:
- `800` ≈ ~10 s at ~80 Hz
- `1600` ≈ ~20 s at ~80 Hz

### `viewer.window_seconds`
- **Type:** float, seconds
- **Default:** `10.0`
- **Meaning:** Desired approximate visible time span.
- **Valid range:** `> 0`
- **Practical range:** `2.0` to `60.0`
- **Notes:** Only used when `viewer.window_samples` is `null`.
- **Conversion:** `ceil(window_seconds * expected_rate_hz)`

### `viewer.expected_rate_hz`
- **Type:** float, Hz
- **Default:** `80.0`
- **Meaning:** Expected source rate used only to convert seconds into sample count.
- **Valid range:** `> 0`
- **Practical range:** around your real device rate
- **Notes:** This does **not** force the stream to be regular.

### `viewer.refresh_s`
- **Type:** float, seconds
- **Default:** `0.05`
- **Meaning:** UI refresh period.
- **Valid range:** `> 0`
- **Practical range:** `0.02` to `0.2`
- **Lower values:** smoother display, more CPU usage.
- **Higher values:** less CPU usage, more sluggish display.

### `viewer.raw_unit_label`
- **Type:** string
- **Default:** `g`
- **Meaning:** Y-axis label for the raw signal panel.
- **Typical values:** `g`, `N`, `kgf`, `ADC`, etc.
- **Notes:** Display-only. It does not rescale data.

### `viewer.filtered_unit_label`
- **Type:** string
- **Default:** `g`
- **Meaning:** Y-axis label for the filtered signal panel.
- **Typical values:** same as the raw signal unit unless DSP changes the unit.
- **Notes:** Display-only.

### `viewer.dt_unit_label`
- **Type:** string
- **Default:** `ms`
- **Meaning:** Y-axis label for the sample-interval panel.
- **Typical values:** `ms`
- **Notes:** Display-only. The internal calculation is `diff(device_clock_us) / 1000.0`.

---

## `reference`

### `reference.csv_path`
- **Type:** path or `null`
- **Default:** `null`
- **Required for:** `mode=csv_replay`
- **Optional for:** `mode=live_with_reference_validation`
- **Meaning:** Bridge CSV file path.

### `reference.xdf_path`
- **Type:** path or `null`
- **Default:** `null`
- **Required for:** `mode=xdf_replay`
- **Optional for:** `mode=live_with_reference_validation`
- **Meaning:** LabRecorder XDF file path.

### `reference.inspect_in_replay_modes`
- **Type:** boolean
- **Default:** `false`
- **Meaning:** If `true`, the viewer will also run the lightweight CSV/XDF inspection step in replay modes before starting playback.
- **Recommendation:** leave `false` unless you specifically want extra metadata logging.

---

## `replay`

### `replay.speed`
- **Type:** float
- **Default:** `1.0`
- **Valid range:** `> 0`
- **Meaning:** Playback speed multiplier.
- **Examples:**
  - `1.0` = real time
  - `2.0` = two times faster
  - `0.5` = half speed

### `replay.loop`
- **Type:** boolean
- **Default:** `false`
- **Meaning:** Whether the replay restarts automatically at the end.

### `replay.start_offset_s`
- **Type:** float, seconds
- **Default:** `0.0`
- **Valid range:** `>= 0`
- **Meaning:** Skip the beginning of the recording and start replaying from this relative offset.

### `replay.time_column`
- **Type:** string
- **Default:** `auto`
- **Used by:** CSV replay only
- **Allowed values:** `auto`, `index`, or any CSV column name
- **Meaning:** Selects which CSV column defines replay time.
- **Auto resolution order:**
  1. `lsl_timestamp_s`
  2. `device_clock_us`
  3. `host_unix_time_ns`
  4. `index` if fallback is enabled

### `replay.time_column_unit`
- **Type:** string
- **Default:** `auto`
- **Used by:** CSV replay only
- **Allowed values:** `auto`, `seconds`, `microseconds`, `nanoseconds`
- **Meaning:** Required only when the chosen time column name does not already imply units.

### `replay.allow_index_fallback`
- **Type:** boolean
- **Default:** `true`
- **Used by:** CSV replay only
- **Meaning:** Allows replay to fall back to sample index divided by `viewer.expected_rate_hz` when no time column is found.
- **Recommendation:** keep `true` for robustness, set `false` when you want strict timebase validation.

---

## Notes on timing

For live irregular streams, MNE-LSL treats:

- `bufsize` as **samples**
- `winsize` as **samples**

That is why this viewer sizes the live window in samples instead of dividing by `sfreq`. This matches the MNE-LSL API for irregular streams. citeturn789503search0turn789503search8

---

## Practical tuning guidance

### Live modes (`mode=live`, `mode=live_with_reference_validation`)

- Start with `viewer.window_seconds=10.0` and `viewer.expected_rate_hz=80.0`. That yields an effective visible window of about `800` samples, which is a good default for handgrip inspection.
- Keep `stream.buffer_samples` at about **2x to 4x** the visible window. With the defaults, `1600` is appropriate. Increase it if the UI occasionally stalls or if you want more tolerance to scheduling jitter.
- Use `stream.acquisition_delay=0.005` to `0.02` for normal operation. Lower values reduce perceived lag but increase CPU wakeups. Higher values reduce overhead but make the display feel less responsive.
- Use `viewer.refresh_s=0.03` to `0.10` for most sessions. Below that, the UI can spend more time repainting than adding value. Above that, short transients become harder to inspect interactively.
- Set `stream.source_id` whenever more than one matching LSL stream may exist on the network. It is the safest way to avoid attaching to the wrong stream.
- Treat `viewer.expected_rate_hz` only as a **display-sizing helper**. It does not change the actual live acquisition rate, and it should not be used to infer authoritative timing.

### CSV replay (`mode=csv_replay`)

- Prefer `replay.time_column=auto` unless you are deliberately testing a specific timebase.
- If the bridge CSV contains `lsl_timestamp_s`, keep it as the replay time source. It is usually the best representation of the host-side LSL timeline.
- If you need to inspect device-side timing behavior, force `replay.time_column=device_clock_us` and set `replay.time_column_unit=microseconds`.
- Keep `replay.allow_index_fallback=true` for convenience while iterating on the bridge schema. Set it to `false` when you want strict validation and would rather fail than silently use an inferred timebase.
- Use `replay.speed=2.0` to `8.0` for rapid screening of long sessions, and return to `1.0` when checking timing-sensitive behavior.

### XDF replay (`mode=xdf_replay`)

- Use XDF replay when the question is about **what LabRecorder persisted**, not just what the bridge emitted.
- Keep `stream.name` / `stream.stype` aligned with the bridge metadata, and set `stream.source_id` if multiple similar streams may exist in the recording.
- Use XDF replay as the authoritative offline check for recorder fidelity, stream selection, and channel labels.

### Validation mode (`mode=live_with_reference_validation`)

- Use this mode after any change to the bridge schema, filter pipeline, channel labels, stream identifiers, or recording workflow.
- Keep `reference.csv_path` and `reference.xdf_path` pointed to the artifacts from the same acquisition session whenever possible.
- Do **not** use validation mode as your default daily monitoring mode unless you are actively debugging integration, because it adds extra inspection work without improving the live source itself.

---

## Failure modes to expect

### Live-stream failures

- **No stream found:** the bridge is not running, the network is isolated, or `stream.name` / `stream.stype` / `stream.source_id` do not match.
- **Wrong stream selected:** multiple LSL streams share the same name/type and `stream.source_id` was left null.
- **Channel-label mismatch:** the live stream exists, but the labels do not match `channels.clock_label`, `channels.raw_label`, or `channels.filtered_label`.
- **Display feels jumpy or laggy:** `stream.buffer_samples`, `stream.acquisition_delay`, and `viewer.refresh_s` are poorly balanced for the machine load.
- **Sparse or bursty updates:** expected with irregular streams if the upstream serial or bridge path is bursty. This is why the device interval panel exists.

### Replay failures

- **CSV replay starts but timing looks wrong:** the wrong time column was auto-selected, units were inferred incorrectly, or replay fell back to index-based timing.
- **CSV replay cannot start:** no usable time column was found and `replay.allow_index_fallback=false`.
- **XDF replay cannot start:** `pyxdf` is not installed, the file path is wrong, or the target stream cannot be uniquely matched.
- **Replay stream selected incorrectly inside XDF:** multiple streams match name/type and `stream.source_id` is missing.

### Cross-artifact validation failures

- **CSV and XDF disagree on channel identity:** usually indicates a schema drift between bridge output and recorded metadata.
- **Bridge CSV looks correct but XDF replay does not:** likely points to recording-side selection, recorder timing, or stream metadata issues rather than the bridge transport itself.
- **Live view is correct but replay is not:** usually indicates an artifact-selection or replay-timebase problem, not a live plotting issue.

### Operational expectations

- The viewer is a visualization and inspection tool. It is not the authoritative offline analysis pipeline.
- Minor visual differences between live mode and replay mode can occur because the live path consumes the current stream ring buffer while replay modes reconstruct timing from persisted artifacts.

---

## Recommended operating workflow

### 1. Normal acquisition

Use this for regular data collection:

1. Start `LSL_Bridge`
2. Start the viewer with `mode=live`
3. Confirm that raw, filtered, and device-interval panels are behaving as expected
4. Start LabRecorder if you want a persisted XDF
5. Run the acquisition session

Recommended command:

```bash
uv run python handgrip_realtime_viewer.py mode=live
```

### 2. Integration / schema validation

Use this after any bridge, protocol, filter, or metadata change:

1. Run a short acquisition with the bridge and LabRecorder
2. Start the viewer with `mode=live_with_reference_validation`
3. Point `reference.csv_path` and `reference.xdf_path` to the artifacts from that same run
4. Confirm that the live stream matches the persisted artifacts semantically

Recommended command:

```bash
uv run python handgrip_realtime_viewer.py   mode=live_with_reference_validation   reference.csv_path=./data/handgrip_samples.csv   reference.xdf_path=./data/session01.xdf
```

### 3. Fast offline bridge review

Use this when the question is mainly about the bridge output or filter behavior:

1. Start the viewer with `mode=csv_replay`
2. Use a higher `replay.speed` for screening
3. Drop back to `1.0` when inspecting a specific interval closely

Recommended command:

```bash
uv run python handgrip_realtime_viewer.py   mode=csv_replay   reference.csv_path=./data/handgrip_samples.csv   replay.speed=4.0
```

### 4. Recorder-fidelity review

Use this when the question is about what LabRecorder actually captured:

1. Start the viewer with `mode=xdf_replay`
2. Use the same `stream.name` / `stream.stype` as the bridge
3. Set `stream.source_id` if the recording may contain multiple similar streams

Recommended command:

```bash
uv run python handgrip_realtime_viewer.py   mode=xdf_replay   reference.xdf_path=./data/session01.xdf
```

---

## Final recommendation

Use the viewer in a **mode-specific** way instead of treating CSV/XDF as loosely attached optional files:

- Use `mode=live` as the default operational mode during acquisition.
- Use `mode=live_with_reference_validation` immediately after any bridge or recording-contract change.
- Use `mode=csv_replay` for the fastest offline inspection of bridge output and placeholder-DSP behavior.
- Use `mode=xdf_replay` when the goal is to verify recorder fidelity or reproduce exactly what was persisted by LabRecorder.

For day-to-day work, the most efficient pattern is:

1. monitor in `live`
2. record XDF in parallel when needed
3. validate with `live_with_reference_validation` after contract changes
4. use `csv_replay` for quick offline triage
5. use `xdf_replay` for final recorder-side confirmation

This keeps the acquisition path, validation path, and replay path conceptually separate, which is the cleanest match to the latest bridge and viewer artifacts.
