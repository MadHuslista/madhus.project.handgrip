# Handgrip Technical Documentation

This document describes the checked-in implementation for both:

- `Device_Application/` — online exercise-event extraction and force reporting.
- `Device_Calibration/` — offline coefficient generation for counts-to-kilograms conversion.

It was written from the repository sources, the provided `Binnacle.md`, the calibration datasets, and external primary documentation for the ATmega328P, Arduino UNO R3, and HX71x-family ADC timing/protocol behavior.

---

## 1. Epistemic Status and Scope

### Known from repository evidence
- Both Arduino sketches configure the ATmega328P SPI peripheral in **slave mode** and assemble incoming data in **3-byte words**, which are then converted from **24-bit two's-complement** format into signed `int32_t` values.
- `Device_Calibration` streams serial records for offline fitting.
- `Device_Application` applies a startup offset (`intercept`), scales raw counts to kilograms, detects start/end events from discrete derivatives, tracks the maximum sample during an active grip, and emits both the full active time series and summary markers.
- The state machine uses the four state codes requested in this README: `-2`, `-1`, `0`, `1`.

### Known from `Binnacle.md`
- The reverse-engineering notes identify the original handgrip front-end as **HX710B** and describe tapping the digital lines between that IC and the original device MCU (`DOUT` and `PD_SCK`).
- The notes explicitly describe the design intent for the application phase: use **first discrete derivative** for start/end detection, track the maximum, clamp very small values around zero, and emit serial tags.

### Known from external primary references
- HX711-class devices output **24-bit two's-complement** data on `DOUT` and are clocked through `PD_SCK`; `PD_SCK` is an **input**, `DOUT` is an **output**, and the interface is a simple two-wire serial timing interface rather than a full, standards-complete SPI peripheral.
- The Arduino UNO / ATmega328P maps SPI to digital pins **10=SS, 11=MOSI, 12=MISO, 13=SCK** and defines the `SPCR` bits used by the firmware (`SPIE`, `SPE`, `DORD`, `MSTR`, `CPOL`, `CPHA`).

### Important uncertainty that must remain explicit
- The user request refers to **HX711**, while the binnacle repeatedly identifies **HX710B**. Both parts belong to the same general HX71x family and both use a compatible `PD_SCK`/`DOUT` serial readout with 24-bit two's-complement output, but they are **not identical parts**.
- Therefore, this README documents the acquisition layer as **HX71x-compatible** and calls out when a statement is verified specifically from the binnacle versus from the HX711 datasheet.
- The repository does **not** include a board BOM, schematic, or package photograph that conclusively proves which exact IC is populated on the handgrip PCB.

### Consequence for interpretation
The checked-in Arduino code should be understood as an **interception/sniffing implementation**, not as a conventional “Arduino directly controlling an HX711 module” driver. The original handgrip electronics continue to generate the clocking activity; the Arduino is configured as a slave receiver on a timing-compatible serial stream.

---

## 2. Repository Layout

```text
Handgrip/
├── Device_Application/
│   └── Firmware/main.ino
├── Device_Calibration/
│   ├── Firmware/write_calibration_data.ino
│   ├── Scripts/read_calibration_data.py
│   ├── Scripts/apply_linear-regression.py
│   └── Data/
└── README.md
```

---

## 3. Evidence Base Used for This README

### Repository files
- `Device_Application/Firmware/main.ino`
- `Device_Calibration/Firmware/write_calibration_data.ino`
- `Device_Calibration/Scripts/read_calibration_data.py`
- `Device_Calibration/Scripts/apply_linear-regression.py`
- `Device_Calibration/Data/*.csv`
- `../Binnacle.md`

### Primary external references
- Arduino UNO R3 user manual / pinout: `https://docs.arduino.cc/resources/datasheets/A000066-datasheet.pdf`
- ATmega328P datasheet: `https://ww1.microchip.com/downloads/en/DeviceDoc/Atmel-7810-Automotive-Microcontrollers-ATmega328P_Datasheet.pdf`
- HX711 datasheet used only to validate the **24-bit two's-complement `PD_SCK`/`DOUT` serial behavior**: `https://cdn.sparkfun.com/datasheets/Sensors/ForceFlex/hx711_english.pdf`

### Notes on binnacle links
`Binnacle.md` contains many exploratory side-track links (Raspberry Pi, GPIO, MQTT, etc.). Those were reviewed for context, but they do **not** constrain the checked-in Arduino implementation and are therefore not used as normative references in this documentation.

---

## 4. System Architecture Overview

### 4.1 Shared Physical / Signal Topology

The implementation is best modeled as the following chain:

```text
Load-cell bridge(s)
    -> HX71x-compatible ADC front-end on original handgrip PCB
        -> Original handgrip MCU provides clocking / read sequence
            -> Arduino taps the digital stream as an SPI slave listener
                -> Arduino firmware converts 24-bit words to signed counts
                    -> Either:
                       (a) calibration serial streaming, or
                       (b) event detection + kilograms output
```

### Why this matters
The user request asked for the “SPI interface between the Arduino (slave) and HX711 sensor (master)”. That is **not** the most accurate hardware description.

- On HX711/HX710B-class devices, `PD_SCK` is a **clock input** to the ADC and `DOUT` is the ADC's serial **output**.
- Therefore the ADC is **not** the clock master in the classical SPI sense.
- The repository code makes the Arduino a **slave receiver** because it is tapping an already-existing exchange on the handgrip PCB instead of originating it.

`Binnacle.md` supports this topology by identifying `DOUT` and `PD_SCK` between the ADC and the handgrip CPU and by explicitly planning to solder out those lines.

---

## 5. Device_Application Architecture

### 5.1 Purpose
`Device_Application/Firmware/main.ino` implements **real-time grip exercise monitoring and event detection**.

Its functional outputs are:
- start marker,
- end marker,
- maximum-force marker,
- calibrated force in kilograms,
- point-by-point time-series data during the active grip.

### 5.2 Input
The firmware receives a stream of **3 bytes per sample** through the ATmega328P SPI peripheral in slave mode and converts them into a signed `int32_t` sample.

### Verified low-level properties
- Word width: 24 bits (`buf[3]`)
- Byte order: MSB first (`DORD = 0` in `SPCR`)
- Signed representation: two's complement (`concat_convert()`)
- Transport interpretation in the firmware: SPI-compatible slave reception on pins `MOSI`, `MISO`, `SCK`, and an auxiliary end-of-frame indicator on pin 9 (`SSpin`)

### Sensor naming note
The code only proves a **24-bit signed serial stream**. The exact front-end part number is ambiguous in the repo:
- request wording: HX711
- binnacle wording: HX710B

For architecture purposes, the safe statement is:

> The application consumes **HX71x-compatible 24-bit signed bridge-converter output** transported over a `PD_SCK`/`DOUT` timing scheme that the Arduino samples through its SPI slave peripheral.

### 5.3 Output protocol
During an active grip, the application emits **live point records** through `Sender(signal_mask, ...)` and, at end-of-grip, emits a **3-row summary block** through `Sender(info)`.

### Live point record format
```text
mask_type<TAB>mask<TAB>point<TAB>raw_count<TAB>kilograms
```

For live points:
- `mask_type = signal_mask = 4`
- `mask` is one of:
  - `1` start sample,
  - `0` middle sample,
  - `-1` end sample

### Summary block format
Three rows are sent after end-of-grip:
- start row
- maximum row
- end row

Each row is stored in `info[row][5]` as:

```text
[data_mask, event_mask, point_index, raw_count, kilograms]
```

where `data_mask = 3` and `event_mask` is:
- `1` start,
- `2` maximum,
- `-1` end.

### 5.4 End-to-end data flow

### Stage A — Byte reception
1. `ISR(SPI_STC_vect)` runs every time a byte completes on SPI.
2. The byte is read from `SPDR`.
3. It is stored into `buf[pos++]`.
4. When 3 bytes have arrived, the code raises `SSpin` and sets `process_it = true`.

### Stage B — 24-bit signed reconstruction
1. `concat_convert(buf)` concatenates the three bytes into a 24-bit value packed inside a `uint32_t`.
2. It checks bit `0x800000` to determine the sign.
3. If negative, it sign-extends using `0xFF000000` and converts to signed decimal.

### Stage C — startup offset calibration
For the first `calib = 10` samples after power-up:
1. `calibration(init_read)` accumulates the mean startup value into `intercept`.
2. In `main.ino`, this mean becomes the runtime offset used by `scalation()`.
3. The first derivative history (`prev_d0`, `prev_d1`) is initialized from that offset.

### Stage D — force scaling
Scaled force is computed as:

```cpp
float y = (gradient / 100000.0) * (x - intercept);
```

where:
- `x` is the raw signed count,
- `intercept` is the startup zero reference,
- `gradient` is the offline-calibrated slope constant stored in firmware.

Then a near-zero clamp is applied:

```cpp
y = y * ((y > clamp_val) + (y < -clamp_val));
```

This means values inside `[-clamp_val, +clamp_val]` become zero.

### Stage E — derivative computation
After calibration is complete, every new sample computes:

```cpp
dd1 = deci - prev_d0;
dd2 = dd1 - prev_d1;
```

where:
- `dd1` is the first discrete derivative,
- `dd2` is the second discrete derivative of the raw-count sequence.

### Stage F — start detection
A grip starts when all of the following are true:

```cpp
end_press && (dd1 > dd1_th) && (deci > -deci_th)
```

Interpretation:
- the previous grip must be closed (`end_press == true`),
- the raw signal must be rising quickly enough (`dd1 > 10000`),
- the sample must be above the configured negative-region threshold (`deci > -150000`).

Actions on start:
- `start_press = true`
- `end_press = false`
- `record_sig = 1`
- `rec_point = 0`
- start row stored into `info[0]`
- the first live record is tagged with `st_mask = 1`

### Stage G — peak tracking
While `start_press == true`, the firmware continuously updates the “true peak” slot whenever:

```cpp
if (start_press && (deci > info[1][3]))
```

This is a **running maximum**, not a predictive or windowed peak detector.

Stored peak metadata:
- event mask `max_mask = 2`
- point index at which the maximum occurred
- raw count at maximum
- scaled kilograms at maximum

### Stage H — end detection
A grip ends when all of the following are true:

```cpp
start_press &&
(dd1 < 0) &&
(dd2 > 0) &&
(dd1 > -dd1_th) &&
(deci < -deci_th)
```

Interpretation:
- the grip must already be active,
- the signal is descending (`dd1 < 0`),
- the curvature has turned upward (`dd2 > 0`),
- the descending slope magnitude is no larger than `dd1_th`,
- the raw signal has crossed into the negative-region threshold (`deci < -150000`).

Actions on end:
- `start_press = false`
- `end_press = true`
- `record_sig = 0`
- one final live sample is emitted with `end_mask = -1`
- the end row is stored into `info[2]`
- the 3-row summary block (`start`, `max`, `end`) is emitted
- the max slot is reset for the next repetition

### 5.5 Architecture summary diagram

```text
3-byte SPI frame
    -> concat_convert()
        -> signed raw count (deci)
            -> startup mean over first 10 samples -> intercept
            -> scalation(deci) -> kilograms
            -> dd1 / dd2 from raw counts
                -> start detector
                -> running maximum tracker
                -> end detector
                    -> live signal stream
                    -> end-of-grip summary rows
```

---

## 6. Device_Calibration Architecture

### 6.1 Purpose
`Device_Calibration` exists to generate the parameters used later by the application firmware to convert raw counts into kilograms.

The intended output is a linear model of the form:

```text
Kg = intercept_ + coef_ * Value
```

The application firmware then stores the slope in the scaled form:

```text
gradient = coef_ * 100000
```

and uses a runtime startup zero offset (`intercept`) measured at power-on.

### 6.2 Input
The calibration path uses the same 24-bit signed acquisition mechanism as the application path.

Input sequence:
1. Handgrip produces raw sensor counts.
2. Arduino firmware receives the counts.
3. Firmware streams serial lines to the host PC.
4. Python script groups samples under a user-entered reference weight.
5. Regression script fits kilograms as a linear function of counts.

### 6.3 Two-stage calibration workflow

### Stage 1 — Arduino firmware
File: `Device_Calibration/Firmware/write_calibration_data.ino`

Behavior:
- Collect startup zero estimate over 10 samples.
- Then, for every active sample, transmit:

```text
state<TAB>intercept<TAB>deci
```

- On detected power-off, transmit:

```text
0<TAB>404
```

### Stage 2 — Host-side sample labeling
File: `Device_Calibration/Scripts/read_calibration_data.py`

Behavior:
1. Open `/dev/ttyUSB0` at `115200` baud.
2. Read one tab-separated serial line at a time.
3. Ignore or reset on state `0`, `-2`, or `-1`.
4. For state `1`, strip the leading state code and keep only `[Intercept, Value]`.
5. Accumulate `n_samples = 100` samples per segment.
6. Ask the user for the reference weight in kilograms.
7. Append a `Kg` column and concatenate the block into a dataframe.
8. Save when user enters `-1`; ignore the segment if user enters `-2`.

### Stage 3 — Offline linear regression
File: `Device_Calibration/Scripts/apply_linear-regression.py`

Behavior:
1. Load `calib_session.csv`.
2. Use `Value` as the independent variable.
3. Use `Kg` as the dependent variable.
4. Fit `sklearn.linear_model.LinearRegression`.
5. Print:
   - `R²`,
   - `model.intercept_`,
   - `model.coef_[0]`,
   - `model.intercept_ / model.coef_[0]`.

### 6.4 Data flow mapping

```text
Raw 24-bit signed count
    -> serial stream from Arduino
        -> [Intercept, Value] sample pairs on host PC
            -> user attaches known Kg reference to each segment
                -> CSV dataset
                    -> linear regression
                        -> slope (kg/count) and intercept (kg-axis)
                            -> firmware gradient constant (scaled by 100000)
```

### 6.5 Important implementation nuance
The calibration firmware and the application firmware treat `intercept` differently:

- In both cases, `intercept` is the **startup zero estimate in raw counts**.
- In the Python regression script, `intercept_` means the **model intercept in kilograms**.

These are two different quantities that happen to use the same English word.

---

## 7. Low-Level SPI / Serial Capture Protocol

### 7.1 Hardware configuration

### Arduino pin mapping used by the sketches
| Signal role in this project        | Arduino UNO / ATmega328P pin | Firmware evidence                           | Notes                                                                                                     |
| ---------------------------------- | ---------------------------: | ------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| Data input from tapped stream      |                   D11 / MOSI | sketch comments and SPI slave configuration | The Arduino receives serial data on MOSI because it is acting as the slave listener.                      |
| Unused data output                 |                   D12 / MISO | `pinMode(MISO, OUTPUT)`                     | Required by AVR SPI slave setup even though the project is receive-centric.                               |
| Clock input from tapped stream     |                    D13 / SCK | sketch comments and SPI slave configuration | External system clocks the incoming bytes.                                                                |
| Hardware SPI SS pin                |                     D10 / SS | not explicitly used in logic                | Present on the MCU/board, but the checked-in logic does not use it as the application-level frame marker. |
| Auxiliary frame-complete indicator |                 D9 / `SSpin` | `int SSpin = 9;`                            | Application-defined signal driven LOW while accumulating bytes and HIGH when a 3-byte word is complete.   |

### 7.2 Role of `SSpin` (pin 9)
`SSpin` is **not** the ATmega328P hardware SPI `SS` pin.

In this repo it is used as a **software-defined end-of-word indicator**:
- set LOW in `setup()` and after each processed frame,
- set HIGH when the third byte of the 24-bit word has arrived.

So its role is:
- **not** bus arbitration,
- **not** peripheral selection,
- **yes** frame-complete signaling for this custom interception setup.

That behavior directly matches the binnacle note about “simulating SS” to synchronize multi-byte reception.

### 7.3 `SPCR` configuration decoded
The sketches program the SPI Control Register (`SPCR`) as follows:

```cpp
SPCR |= 0x80; // SPIE
SPCR |= 0x40; // SPE
SPCR &= 0xDF; // clear DORD
SPCR &= 0xEF; // clear MSTR
SPCR &= 0xF7; // clear CPOL
SPCR |= 0x04; // set CPHA
```

### Meaning of each magic number
| Operation      |         Mask | Register bit affected | Meaning                          |
| -------------- | -----------: | --------------------- | -------------------------------- |
| `SPCR          |      = 0x80` | `1000 0000b`          | `SPIE` (bit 7)                   | Enable SPI transfer-complete interrupt.             |
| `SPCR          |      = 0x40` | `0100 0000b`          | `SPE` (bit 6)                    | Enable the SPI peripheral.                          |
| `SPCR &= 0xDF` | `1101 1111b` | clears `DORD` (bit 5) | Select MSB-first transfer order. |
| `SPCR &= 0xEF` | `1110 1111b` | clears `MSTR` (bit 4) | Select **slave mode**.           |
| `SPCR &= 0xF7` | `1111 0111b` | clears `CPOL` (bit 3) | Idle clock polarity LOW.         |
| `SPCR          |      = 0x04` | `0000 0100b`          | sets `CPHA` (bit 2)              | Sample on trailing edge when `CPOL=0` (SPI mode 1). |

### Resulting SPI mode
The final configuration is:
- `CPOL = 0`
- `CPHA = 1`

That is **SPI mode 1** on ATmega328P terminology.

### Why mode 1 is used here
The binnacle reasoning is consistent with HX71x behavior:
- the clock idles low,
- the ADC data shifts with positive clock activity,
- the receiving side samples on the trailing edge.

### 7.4 Interrupt service routine behavior
The ISR is:

```cpp
ISR(SPI_STC_vect) {
    byte c = SPDR;

    if (pos < sizeof(buf)) {
        buf[pos++] = c;
        if (pos == sizeof(buf)) {
            digitalWrite(SSpin, HIGH);
            process_it = true;
        }
    }
}
```

### Operational sequence
1. AVR hardware completes one SPI byte transfer.
2. `SPIF` is set by the SPI peripheral.
3. Because `SPIE=1`, `ISR(SPI_STC_vect)` executes.
4. The byte is read from `SPDR`.
5. The byte is stored in `buf[0]`, `buf[1]`, or `buf[2]`.
6. On the third byte, `process_it` becomes `true`.
7. The main loop later consumes the complete 24-bit word and resets `pos` to `0`.

### 7.5 3-byte word assembly
The firmware intentionally stores exactly 3 bytes because the ADC word is 24 bits:

```cpp
unsigned char buf[3];
```

This is consistent with the HX711/HX710B family output format.

### 7.6 `concat_convert()` conversion path
The conversion function is:

```cpp
uint32_t val = ((uint32_t)buffer[0] << 16)
             | ((uint32_t)buffer[1] << 8)
             | ((uint32_t)buffer[2] << 0);

uint32_t sign_mask = 0x800000;

if ((val & sign_mask) == 0) {
    return val;
} else {
    return -(~(val | 0xFF000000) + 1);
}
```

### Step-by-step explanation
1. The three bytes are packed into the lower 24 bits of a `uint32_t`.
2. `0x800000` checks the sign bit of the 24-bit word.
3. If the sign bit is clear, the value is already a positive integer.
4. If the sign bit is set, the code first sign-extends the upper byte with `0xFF000000`.
5. It then performs two's-complement magnitude recovery and negation.

### Meaning of the magic numbers
|        Value | Meaning                                                                                           |
| -----------: | ------------------------------------------------------------------------------------------------- |
|   `0x800000` | Sign-bit mask for bit 23 of a 24-bit word.                                                        |
| `0xFF000000` | Upper-byte padding mask used to sign-extend the 24-bit negative number inside a 32-bit container. |

### Range implication
A 24-bit signed two's-complement word spans:
- minimum: `0x800000`
- maximum: `0x7FFFFF`

That exact saturation range is explicitly documented in HX711-class datasheets and also discussed in the binnacle.

---

## 8. Application Event Logic and State Machine

### 8.1 State definitions
| State code | Meaning                                                                    | Where used    |
| ---------: | -------------------------------------------------------------------------- | ------------- |
|       `-2` | Device off / idle / pre-data state                                         | Both sketches |
|       `-1` | Startup calibration completed, waiting for first active acquisition sample | Both sketches |
|        `0` | Power-off event detected after inactivity timeout                          | Both sketches |
|        `1` | Active data acquisition                                                    | Both sketches |

### 8.2 State transition logic
The state machine is not implemented as an explicit `switch` statement; it is inferred from the `if / else if` chain in the `loop()` idle branch.

### Transition summary
1. **Boot / reset**
   - `calib = 10`
   - `data_acq = 0`
   - `state = -2`

2. **Startup calibration completes**
   - after the first 10 samples have been averaged,
   - `calib == 0`
   - but no active post-calibration sample has been acquired yet,
   - so state becomes `-1`.

3. **Active acquisition**
   - once live samples are arriving after calibration,
   - `data_acq = 1`
   - `st_time = millis()` is refreshed on every sample,
   - state becomes `1` while the gap since last sample is `< 100 ms`.

4. **Ambiguous inactivity window**
   - if no new sample arrives and the gap exceeds `150 ms` but is still below `200 ms`,
   - the code records `calib_prob = present_value`.
   - This is used to repair an improper startup sequence (see below).

5. **Power-off event**
   - if no new sample arrives for `>= 200 ms`,
   - state becomes `0`,
   - serial emits `0<TAB>404`,
   - calibration counters are reset for the next cycle.

### 8.3 `calib_prob` recovery mechanism
`calib_prob` is a corrective mechanism for a special failure/ambiguity case described in the source comments:

> the device may have entered the calibration phase without a clean prior “off” detection, which makes “waiting for first data” and “device turned off before data” look similar.

### What the recovery does
If the firmware later sees that data acquisition has resumed while `calib_prob` is populated:
- it retroactively resets the logical state to the equivalent of “device was actually off,”
- it sets `data_acq = 0`,
- it restores `calib = 8`,
- it seeds `intercept` with the first two relevant values:

```cpp
intercept = calib_prob / 10.0 + present_value / 10.0;
```

### Interpretation
This is a **state-repair heuristic**, not a mathematically clean estimator. Its purpose is to preserve behavioral consistency when the external handgrip startup sequence does not cleanly align with the Arduino observer's expected off→calibration→acquisition progression.

---

## 9. Magic Numbers Documentation

### 9.1 Calibration-related constants
| Constant                        | Location                  | Meaning                                                                                                                                                                                                    |
| ------------------------------- | ------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `calib = 10`                    | both firmware files       | Use the first 10 samples after startup to estimate the zero offset (`intercept`).                                                                                                                          |
| `-225800 < intercept < -169600` | calibration firmware only | Acceptable raw-count window for the startup offset; if violated, fallback to `-195680`. The comment calls this “(-1Kg < intercept < 1Kg)”, but the values themselves are in **raw counts**, not kilograms. |
| `-195680`                       | calibration firmware only | Fallback zero-count reference used if the startup average is outside the accepted window.                                                                                                                  |

### Important nuance
The application firmware has this intercept-range clamp **commented out**, so the runtime application path currently trusts the 10-sample average directly.

### 9.2 Thresholds and derived-signal constants
| Constant           | Meaning                                                                                 |
| ------------------ | --------------------------------------------------------------------------------------- |
| `dd1_th = 10000`   | Start/end derivative magnitude threshold in raw counts per sample.                      |
| `deci_th = 150000` | Raw-count threshold separating the upper and lower regions used by the start/end logic. |
| `clamp_val = 0.1`  | Near-zero deadband in kilograms; values inside ±0.1 kg are forced to zero.              |

### Binnacle consistency
The 0.1 kg clamp matches the binnacle note “Clampar la detección a 100gr”.

### 9.3 Timing constants
| Constant | Meaning                                                                                    |
| -------- | ------------------------------------------------------------------------------------------ |
| `100 ms` | Gap threshold below which the device is still considered actively acquiring (`state = 1`). |
| `150 ms` | Start of the ambiguity window used to populate `calib_prob`.                               |
| `200 ms` | Definitive inactivity threshold interpreted as power-off (`state = 0`).                    |

### 9.4 State codes and sentinels
| Value | Meaning                                                                 |
| ----: | ----------------------------------------------------------------------- |
|  `-2` | Device off / idle                                                       |
|  `-1` | Post-calibration wait                                                   |
|   `0` | Power-off event detected                                                |
|   `1` | Active data acquisition                                                 |
| `404` | Serial sentinel emitted alongside state `0` to indicate power-off event |

### 9.5 Event / record masks
| Constant      | Value | Meaning                        |
| ------------- | ----: | ------------------------------ |
| `st_mask`     |   `1` | Start event                    |
| `mid_mask`    |   `0` | Middle / regular active sample |
| `end_mask`    |  `-1` | End event                      |
| `max_mask`    |   `2` | Maximum event                  |
| `data_mask`   |   `3` | Summary-row class              |
| `signal_mask` |   `4` | Live-stream-row class          |

### 9.6 Scaling constants
| Constant     |         Value | Meaning                                                            |
| ------------ | ------------: | ------------------------------------------------------------------ |
| `gradient`   |       `3.575` | Hard-coded slope constant stored in “kg-per-count × 100000” units. |
| `/ 100000.0` | scale divisor | Converts `gradient` into kg/count.                                 |

### Interpreted slope
The effective slope used by firmware is:

```text
3.575 / 100000 = 3.575e-05 kg/count
```

### Repository cross-check
Running the provided regression workflow on `Device_Calibration/Data/calib_session.csv` yields a fitted slope of approximately:

```text
3.594658255e-05 kg/count
```

This is close to, but not identical with, the hard-coded firmware value.

### Epistemic conclusion
- **Known:** the application firmware uses `3.575e-05 kg/count`.
- **Known:** the provided calibration dataset and regression script can produce a nearby slope.
- **Unknown from repo:** the exact derivation chain that produced the final hard-coded `3.575` value.

### 9.7 SPI register masks
|         Mask | Binary            | Meaning                                           |
| -----------: | ----------------- | ------------------------------------------------- |
|       `0x80` | `1000 0000`       | Set `SPIE`                                        |
|       `0x40` | `0100 0000`       | Set `SPE`                                         |
|       `0xDF` | `1101 1111`       | Clear `DORD`                                      |
|       `0xEF` | `1110 1111`       | Clear `MSTR`                                      |
|       `0xF7` | `1111 0111`       | Clear `CPOL`                                      |
|       `0x04` | `0000 0100`       | Set `CPHA`                                        |
|   `0x800000` | `24-bit sign bit` | Check sign of incoming ADC word                   |
| `0xFF000000` | `upper-byte fill` | Sign extension padding for negative 24-bit values |

---

## 10. Calibration Workflow Documentation

### 10.1 Firmware stage
`write_calibration_data.ino` reuses the shared SPI-capture core and emits serial data suitable for offline labeling.

### Serial behavior by state
- `-2`, `-1`: transitional / idle states, printed and then ignored by the host collector.
- `1`: active acquisition, host collector keeps `[Intercept, Value]`.
- `0`: power-off sentinel, host collector resets and discards the partial segment.

### 10.2 Host collection stage
`read_calibration_data.py` creates a dataframe with columns:

| Column      | Meaning                                             |
| ----------- | --------------------------------------------------- |
| `Intercept` | Startup zero-count estimate reported by firmware    |
| `Value`     | Current raw-count sample                            |
| `Kg`        | User-entered reference mass for the current segment |

### Segment control values entered by the user
|                 User input | Meaning                                                     |
| -------------------------: | ----------------------------------------------------------- |
| any positive/real kg value | label current 100-sample segment with that reference weight |
|                       `-1` | save and exit                                               |
|                       `-2` | discard current segment                                     |

### 10.3 Regression stage
`apply_linear-regression.py` performs an ordinary least-squares fit:

```text
Kg = intercept_ + coef_ * Value
```

The printed `intercept_ / coef_` value is the raw-count location where the fitted line crosses zero kilograms (with sign preserved by the code exactly as written).

### 10.4 Binnacle-to-code divergence worth documenting
The binnacle mentions a plan to use **250 points** per stable reference segment. The checked-in Python collector uses **100 samples** (`n_samples = 100`).

That is a real repo-level divergence and should not be silently normalized away.

---

## 11. Cross-Project Relationship

### 11.1 What is shared
The two firmware projects share the same lower-level acquisition stack:
- SPI slave configuration,
- 3-byte buffering,
- 24-bit signed conversion,
- startup zero estimation,
- basic state machine.

### 11.2 What differs
| Aspect                  | Device_Calibration                           | Device_Application                                    |
| ----------------------- | -------------------------------------------- | ----------------------------------------------------- |
| Goal                    | collect labeled raw data for offline fitting | detect grip events and report exercise metrics online |
| Output                  | state/intercept/raw count stream             | live signal rows + summary rows with kilograms        |
| Peak logic              | none                                         | running maximum during active grip                    |
| Start/end logic         | none beyond device-state handling            | derivative-based event detection                      |
| Intercept sanity clamp  | active                                       | commented out                                         |
| Clamp around zero in kg | helper exists but not central                | active and behaviorally important                     |

---

## 12. Implementation Notes and Caveats

### 12.1 The ADC interface is SPI-like, not generic SPI in the full bus sense
The repo uses the AVR SPI peripheral because the tapped stream is timing-compatible with SPI mode 1, but HX71x devices expose a specialized `PD_SCK`/`DOUT` serial interface with frame-length semantics (`25–27` pulses on HX711-class devices), not a full general-purpose SPI peripheral with standard chip-select framing.

### 12.2 The “true peak” is a running maximum
The code comment says “True Peak Detection”, but the actual algorithm is a simple running max over the active segment:

```cpp
if (start_press && (deci > info[1][3]))
```

No prediction, interpolation, or refractory window is implemented in the checked-in code.

### 12.3 The application and calibration use the word `intercept` for different concepts
This is the single most important naming collision in the repo:
- firmware `intercept`: startup zero-count offset,
- regression `intercept_`: y-axis intercept of the fitted line in kilograms.

### 12.4 The application source contains a stray token
`Device_Application/Firmware/main.ino` contains the text:

```cpp
void loop(){signal_calibration_recording
```

This token does not belong to the functional architecture and appears to be an accidental edit artifact. It should be treated as source noise, not as part of the design.

---

## 13. Recommended Mental Model

If you need one compact interpretation of the whole repository, use this:

> The project taps the handgrip's existing HX71x-style digital load-cell converter stream, reconstructs signed 24-bit samples on an Arduino configured as an SPI slave, estimates zero on startup, converts counts to kilograms using a linear calibration, and then either (a) records calibration data for offline fitting or (b) performs online grip segmentation with start / max / end tagging.

---

## 14. Source Traceability Map

### Repository sources
- `Device_Application/Firmware/main.ino`
  - runtime constants, state logic, derivative logic, event detection, output format
- `Device_Calibration/Firmware/write_calibration_data.ino`
  - calibration streaming path, intercept fallback logic
- `Device_Calibration/Scripts/read_calibration_data.py`
  - host-side segment acquisition and labeling
- `Device_Calibration/Scripts/apply_linear-regression.py`
  - regression model definition
- `Device_Calibration/Data/calib_session.csv`
  - example labeled calibration dataset
- `../Binnacle.md`
  - reverse-engineering rationale, signal measurements, event-detection intent, clamp intent

### External primary references
- Arduino UNO R3 board/pinout: `https://docs.arduino.cc/resources/datasheets/A000066-datasheet.pdf`
- ATmega328P SPI register and timing definitions: `https://ww1.microchip.com/downloads/en/DeviceDoc/Atmel-7810-Automotive-Microcontrollers-ATmega328P_Datasheet.pdf`
- HX711 24-bit format and `PD_SCK`/`DOUT` timing reference: `https://cdn.sparkfun.com/datasheets/Sensors/ForceFlex/hx711_english.pdf`

