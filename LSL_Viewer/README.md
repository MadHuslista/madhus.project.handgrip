# Handgrip Real-Time Viewer

## Purpose

This viewer connects to the **LSL stream emitted by `LSL_Bridge`** and plots the latest data in real time.
It is designed for the current **irregular 3-channel stream**:

1. `device_clock_us`
2. `grip_force_raw`
3. `grip_force_filtered`

It also supports **optional offline reference inspection** for:
- the `.csv` produced by `LSL_Bridge`
- the `.xdf` recorded by LabRecorder

The viewer shows three live panels:
- **raw signal**
- **filtered signal**
- **device sample interval** in milliseconds, computed from `device_clock_us`

---

## Important note about the current artifact state

The uploaded files are currently **not fully aligned**:

- `conf/config.yaml` is written for a **Hydra-based** entrypoint.
- the current uploaded `handgrip_realtime_viewer.py` artifact is still **argparse-based**.

So this README documents the **intended Hydra-style configuration contract** represented by `conf/config.yaml`.
If you want the script to actually consume `conf/config.yaml` directly, the viewer entrypoint must be the Hydra-refactored version.

---

## Expected stream contract

The viewer expects an LSL stream with:

- **name**: typically `ArduinoHandgrip`
- **type**: typically `Force`
- **sampling model**: **irregular** (`sfreq = 0` on the LSL side)
- **channels**:
  - `device_clock_us`
  - `grip_force_raw`
  - `grip_force_filtered`

If one of these channels is missing, the viewer should reject the stream.

---

## Recommended environment

Typical dependencies:

- Python 3.10+
- `mne-lsl`
- `numpy`
- `pandas`
- `matplotlib`
- `hydra-core`
- optionally `pyxdf` for `.xdf` inspection

If you are using `uv`, the typical flow is:

```bash
uv sync
uv run python handgrip_realtime_viewer.py
```

---

## Typical usage

### 1. Start the LSL bridge

Start your `LSL_Bridge` first so the stream is present on the network.

### 2. Start the viewer

With the intended Hydra-style interface:

```bash
uv run python handgrip_realtime_viewer.py
```

### 3. Override parameters from the CLI

Hydra-style overrides:

```bash
uv run python handgrip_realtime_viewer.py stream.name=ArduinoHandgrip stream.stype=Force
```

With reference files:

```bash
uv run python handgrip_realtime_viewer.py \
  reference.csv_path=./handgrip_samples.csv \
  reference.xdf_path=./sub-P001_ses-S001_task-Default_run-001_eeg.xdf
```

Override display window:

```bash
uv run python handgrip_realtime_viewer.py \
  viewer.window_seconds=15 \
  viewer.refresh_s=0.03
```

Pin a specific source instance:

```bash
uv run python handgrip_realtime_viewer.py \
  stream.source_id='arduino-handgrip-1a86-7523-_dev_ttyUSB0'
```

---

## How the viewer interprets time

This viewer is meant for an **irregular stream**.
That matters because:

- the LSL side reports `sfreq = 0`
- the viewer should **not** compute window length from `stream.info["sfreq"]`
- plotting is driven by a **sample count window**, not by assuming a fixed-rate buffer

The viewer uses:
- `viewer.window_samples` **if provided**, otherwise
- `viewer.window_seconds * viewer.expected_rate_hz`

So `expected_rate_hz` is only a **display-sizing helper**, not a claim that the stream is truly regular.

---

## Configuration file

Current config structure:

```yaml
stream:
  name: ArduinoHandgrip
  stype: Force
  source_id: null
  buffer_samples: 1600
  acquisition_delay: 0.01
  timeout: 5.0

channels:
  clock_label: device_clock_us
  raw_label: grip_force_raw
  filtered_label: grip_force_filtered

viewer:
  window_samples: null
  window_seconds: 10.0
  expected_rate_hz: 80.0
  refresh_s: 0.05
  raw_unit_label: g
  filtered_unit_label: g
  dt_unit_label: ms

reference:
  csv_path: null
  xdf_path: null

logging:
  level: INFO

hydra:
  run:
    dir: .
  output_subdir: null
  job:
    chdir: false
```

---

## Parameter reference

## `stream`

### `stream.name`
- **Type:** string
- **Default:** `ArduinoHandgrip`
- **Meaning:** LSL stream name used to resolve/connect to the correct stream.
- **Typical values:** any non-empty string
- **Recommended range:** exact producer stream name
- **Notes:** If multiple streams share the same name, use `stream.source_id` as well.

### `stream.stype`
- **Type:** string
- **Default:** `Force`
- **Meaning:** LSL stream type filter.
- **Typical values:** `Force`, `EEG`, `Markers`, etc., but for this project it should normally stay `Force`.
- **Recommended range:** exact producer stream type
- **Notes:** Must match the bridge metadata.

### `stream.source_id`
- **Type:** string or `null`
- **Default:** `null`
- **Meaning:** Optional unique identifier for one exact LSL source.
- **Typical values:** `null` or a stable unique string
- **Recommended range:** `null` if only one matching stream exists; otherwise set it explicitly.
- **Notes:** Use this when multiple streams with the same `name` and `stype` are present.

### `stream.buffer_samples`
- **Type:** integer
- **Default:** `1600`
- **Meaning:** Ring buffer size used by the LSL client.
- **Valid range:** integer `>= 2`
- **Practical range:** roughly `2x` to `5x` the visible window length in samples
- **Guideline:** For an ~80 Hz stream, `1600` samples is about 20 seconds of storage.
- **Too low:** old data gets overwritten sooner, increased risk of losing context.
- **Too high:** more memory use and slightly more sluggish behavior when debugging.

### `stream.acquisition_delay`
- **Type:** float, seconds
- **Default:** `0.01`
- **Meaning:** Background acquisition polling interval for `mne-lsl`.
- **Valid range:** `> 0`
- **Practical range:** `0.001` to `0.05`
- **Lower values:** lower latency, more CPU wakeups.
- **Higher values:** less CPU overhead, slightly less responsive updates.
- **Recommendation:** keep near `0.005` to `0.02` unless you have a reason to tune it.

### `stream.timeout`
- **Type:** float, seconds
- **Default:** `5.0`
- **Meaning:** Timeout for initial LSL connection.
- **Valid range:** `> 0`
- **Practical range:** `1.0` to `30.0`
- **Lower values:** fail fast if the stream is absent.
- **Higher values:** more tolerant to slow discovery or slow startup.

---

## `channels`

These must match the **actual labels published by the bridge**.

### `channels.clock_label`
- **Type:** string
- **Default:** `device_clock_us`
- **Meaning:** Name of the channel carrying the device clock in microseconds.
- **Recommended value:** exact bridge channel label

### `channels.raw_label`
- **Type:** string
- **Default:** `grip_force_raw`
- **Meaning:** Name of the raw signal channel.
- **Recommended value:** exact bridge channel label

### `channels.filtered_label`
- **Type:** string
- **Default:** `grip_force_filtered`
- **Meaning:** Name of the filtered signal channel.
- **Recommended value:** exact bridge channel label

If any of these labels do not exist in the connected stream, the viewer should fail early.

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
- **Type:** string path or `null`
- **Default:** `null`
- **Meaning:** Optional path to the CSV written by the bridge.
- **Expected file columns:** typically `device_clock_us`, `value_raw`, `value_filtered`
- **Use:** quick schema validation and offline reference inspection
- **Notes:** If set, the viewer logs detected CSV columns.

### `reference.xdf_path`
- **Type:** string path or `null`
- **Default:** `null`
- **Meaning:** Optional path to a LabRecorder `.xdf` file.
- **Use:** inspect stored stream metadata and channel labels
- **Notes:**
  - if `pyxdf` is installed, it performs a real `.xdf` parse
  - otherwise it falls back to a lightweight metadata scan

---

## `logging`

### `logging.level`
- **Type:** string
- **Default:** `INFO`
- **Allowed values:** `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`
- **Meaning:** Viewer log verbosity.
- **Recommendation:**
  - `INFO` for normal use
  - `DEBUG` for stream-resolution or schema debugging

---

## `hydra`

These values control Hydra runtime behavior.

### `hydra.run.dir`
- **Default:** `.`
- **Meaning:** Prevents Hydra from creating a separate per-run output directory.
- **Why used here:** keeps the script behaving like a normal local utility.

### `hydra.output_subdir`
- **Default:** `null`
- **Meaning:** disables Hydra’s default output subdirectory.

### `hydra.job.chdir`
- **Default:** `false`
- **Meaning:** prevents Hydra from changing the working directory at runtime.
- **Why used here:** avoids breaking relative paths for local data files.

---

## Practical tuning guidance

### Stable default for your current setup

For an Arduino stream around 80 Hz:

```yaml
stream:
  buffer_samples: 1600
  acquisition_delay: 0.01
  timeout: 5.0

viewer:
  window_seconds: 10.0
  expected_rate_hz: 80.0
  refresh_s: 0.05
```

This is a good starting point.

### If the UI feels sluggish

Try:

```yaml
viewer:
  refresh_s: 0.02
```

and optionally:

```yaml
stream:
  acquisition_delay: 0.005
```

### If CPU usage is unnecessarily high

Try:

```yaml
viewer:
  refresh_s: 0.1

stream:
  acquisition_delay: 0.02
```

### If you want a longer visible history

Either set an explicit sample window:

```yaml
viewer:
  window_samples: 2400
```

or increase seconds:

```yaml
viewer:
  window_seconds: 30.0
```

If you do that, also consider increasing:

```yaml
stream:
  buffer_samples: 3200
```

so the ring buffer is comfortably larger than the visible window.

---

## Failure modes to expect

### The viewer cannot connect to the stream
Common causes:
- the bridge is not running
- `stream.name` or `stream.stype` is wrong
- multiple similar streams exist and `stream.source_id` was not set

### The viewer connects but rejects the stream
Common causes:
- channel labels do not match `channels.clock_label`, `channels.raw_label`, `channels.filtered_label`
- the connected stream is not the current bridge schema

### The plots appear flat or too narrow
Common causes:
- the live signal has very little variation
- the wrong unit labels are being assumed
- the filter output is not behaving as expected upstream in the bridge

### The device interval panel is noisy
That usually means the Arduino timing or host-side acquisition is irregular, which is exactly why this stream is modeled as irregular.

---

## Recommended operating workflow

1. Start the Arduino / serial producer.
2. Start `LSL_Bridge` and confirm it is publishing:
   - `device_clock_us`
   - `grip_force_raw`
   - `grip_force_filtered`
3. Optionally start LabRecorder.
4. Start the viewer.
5. Optionally provide the generated CSV/XDF as references for validation.

---

## Minimal override examples

Use a different stream name:

```bash
uv run python handgrip_realtime_viewer.py stream.name=MyHandgrip
```

Use a specific source instance:

```bash
uv run python handgrip_realtime_viewer.py stream.source_id=my-device-001
```

Use a 20-second view:

```bash
uv run python handgrip_realtime_viewer.py viewer.window_seconds=20
```

Use a fixed 1200-sample window instead:

```bash
uv run python handgrip_realtime_viewer.py viewer.window_samples=1200
```

Enable debug logs:

```bash
uv run python handgrip_realtime_viewer.py logging.level=DEBUG
```

Add offline references:

```bash
uv run python handgrip_realtime_viewer.py \
  reference.csv_path=./handgrip_samples.csv \
  reference.xdf_path=./sub-P001_ses-S001_task-Default_run-001_eeg.xdf
```

---

## Final recommendation

Treat the viewer config as a **display and stream-resolution contract**, not as a signal-processing contract.
The signal processing should remain in the bridge / DSP module, while the viewer should stay simple:
- connect
- validate channel schema
- display raw / filtered / interval
