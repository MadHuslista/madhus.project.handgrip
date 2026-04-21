# High-Speed Acquisition Instrument  
## Reorganized Markdown Manual for the 96×48 Dual-Display Load-Cell Indicator / Transmitter

**Document purpose.**  
This is a reorganized, clarified Markdown version of the board manual you uploaded, adapted for the specific full-feature AC-powered unit shown in your photos. It preserves the PDF content, fixes the structure, adds practical operating procedures, and explicitly marks places where the original manual is ambiguous because of machine translation.

**What I found on the web.**
- A public duplicate of essentially the same Chinese/English manual is hosted on an AliExpress CDN.
- I did **not** find a richer official manufacturer manual for this exact front panel / terminal map.
- I did find several similar Chinese weighing-transmitter / force-indicator manuals that corroborate the interpretation of:
  - the `10 / 40 / 640 / 1280 Hz` sampling-rate parameter,
  - the speed-vs-stability tradeoff of digital filtering,
  - the use of stability detection before accepting zeroing / calibration.

**Confidence model used in this rewrite.**
- **High confidence:** items explicitly present in the uploaded PDF and your device photos.
- **Medium confidence:** operating procedures reconstructed from the menu structure, key legend, and behavior common to similar instruments.
- **Lower confidence:** places where the source manual is obviously mistranslated or incomplete, especially around “dynamic tracking,” “stable weight,” and some relay / analog-output wording.

---
## Table of Contents

[TOC]

## 1. Product identity and scope

This instrument is a **panel-mount load-cell indicator / transmitter / controller** with:
- dual 5-digit LED displays,
- 1 load-cell input,
- up to 3 relay outputs,
- optional analog output,
- optional RS485,
- optional external digital-input trigger / remote zero-tare input.

The PDF describes four variants:

| Variant             | Included features                              |
| ------------------- | ---------------------------------------------- |
| Basic model         | Dual display, 3 relay outputs, 1 digital input |
| Analog-output model | Basic model + analog output                    |
| RS485 model         | Basic model + RS485                            |
| Full-function model | Basic model + analog output + RS485            |

### Your observed unit
From the rear label and photos, your unit appears to be the **full-function AC-powered model**, with:
- **AC mains input on terminals 19/20**
- **RS485 on terminals 1/2**
- **Analog output on terminals 9/10**
- **Sensor input on terminals 5/6/7/8**
- **External DI on terminals 3/4**
- **Relay outputs on terminals 11–18**

---

## 2. Safety and installation boundaries

1. Use the unit only within its electrical and environmental ratings.
2. Do not open the chassis while powered.
3. If using the AC-powered version, treat terminals `19/20` as mains-voltage terminals.
4. The manual calls for **reliable grounding** and says the grounding scheme should be kept separate from the AC grounding wire. The unit does **not** document a dedicated PE terminal on the terminal block; treat cabinet grounding as a **system-level installation decision**, not as “tie PE to any negative signal terminal.”
5. Keep sensor wiring away from mains and relay wiring.
6. For noisy environments, prefer:
   - twisted pair for sensor signal lines,
   - shielded cable for RS485,
   - separate routing of sensor and AC power wiring.

---

## 3. Technical specifications

| Item                  | Value                                                                                  |
| --------------------- | -------------------------------------------------------------------------------------- |
| Display               | Dual 5-digit LED display                                                               |
| Supply                | `DC 10–28 V` **or** `AC 85–265 V` (rated `100–240 V`, `50/60 Hz`) depending on version |
| Sensor capacity       | Up to 8 × `350 Ω` sensors                                                              |
| Input signal range    | `0.5–3.0 mV/V`                                                                         |
| Excitation voltage    | `5 V`                                                                                  |
| Sampling rates        | `10`, `40`, `640`, `1280 Hz`                                                           |
| Internal ADC          | `24-bit Σ-Δ ADC`                                                                       |
| Internal resolution   | `1 / 1,000,000`                                                                        |
| Display resolution    | `1 / 100,000`                                                                          |
| Nonlinearity          | `0.005 %FS`                                                                            |
| Max power consumption | `5 W`                                                                                  |
| Operating temperature | `-25 °C` to `+45 °C`                                                                   |
| Relative humidity     | `< 85 %RH`                                                                             |
| Approx. weight        | `300 g`                                                                                |
| External size         | `96 × 48 × 110 mm`                                                                     |
| Panel cutout          | `92 × 46 mm`                                                                           |

### Practical meaning of the 4 sampling rates
The manual lists `10 / 40 / 640 / 1280 Hz` but does not explain the tradeoff well. Similar weighing-indicator manuals with the same rate set explain the general rule:

- **Higher sampling rate** → faster response, lower effective noise immunity / less stable display
- **Lower sampling rate** → slower response, better stability

That matches the rest of this board’s menu structure because it also provides median and averaging filters.

---

## 4. Mechanical installation

- Front panel format: **96 × 48 mm**
- Panel cutout: **92 × 46 mm**
- Insert the instrument from the front of the panel.
- Use the included metal rear clamps / brackets to secure it from the back.

### Included mounting clamps
The loose metal parts shipped with the unit are **panel-mount brackets for the display unit**, not load-cell mounting hardware.

---

## 5. Front panel and user interface

### 5.1 Display behavior

- **Main display:** net weight
- **Secondary display:** setting parameter, gross weight, peak value, or unit

### 5.2 Indicators

| Indicator              | Meaning                                           |
| ---------------------- | ------------------------------------------------- |
| `OUT1`, `OUT2`, `OUT3` | Corresponding relay output is active              |
| `PEAK` solid           | Secondary display is currently showing peak value |
| `PEAK` flashing        | Waiting for peak-trigger condition                |

### 5.3 Keys

The source PDF shows icon-only legends. On your front-panel photo, the practical mapping is:

| Key position                                     | Practical name            | Short press                                                                    | Long press                    |
| ------------------------------------------------ | ------------------------- | ------------------------------------------------------------------------------ | ----------------------------- |
| Green `Fn` key                                   | Menu / back               | Enter menu or return to previous level                                         | Enter decimal-point selection |
| First orange key (down-arrow / calibration icon) | Calibration / cursor down | Enter calibration interface or move down / move cursor                         | Zero function                 |
| Second orange key (up-arrow / `T`)               | Up / increment / tare     | Change menu item / increment value                                             | Tare                          |
| Orange `ENT` key                                 | Confirm / display switch  | Confirm in menu; in display mode cycle secondary display (unit / gross / peak) | Clear peak                    |

> **Important note:** The key semantics above are directly supported by the PDF, but the exact symbol-to-key mapping is partly reconstructed from your front-panel photo because the machine-translated PDF drops some icons.

---

## 6. Rear terminals and wiring map

### 6.1 Terminal assignment for the full-function model observed in your photos

| Terminal | Label  | Purpose                                          |
| -------- | ------ | ------------------------------------------------ |
| 1        | `A+`   | RS485 `A` / non-inverting line                   |
| 2        | `B-`   | RS485 `B` / inverting line                       |
| 3        | `DI-`  | External digital input / remote zero-tare return |
| 4        | `DI+`  | External digital input / remote zero-tare input  |
| 5        | `E+`   | Sensor excitation +                              |
| 6        | `E-`   | Sensor excitation -                              |
| 7        | `S-`   | Sensor signal -                                  |
| 8        | `S+`   | Sensor signal +                                  |
| 9        | `AO-`  | Analog output -                                  |
| 10       | `AO+`  | Analog output +                                  |
| 11–12    | `OUT3` | Relay output 3 dry contact                       |
| 13–15    | `OUT2` | Relay output 2 dry contact set                   |
| 16–18    | `OUT1` | Relay output 1 dry contact set                   |
| 19       | `L`    | AC live                                          |
| 20       | `N`    | AC neutral                                       |

### 6.2 Power terminals

The manual says terminals 19 and 20 are the power input:
- **DC version:** `DC+ / DC-`
- **AC version:** `N / L`

Your board label explicitly shows **AC100–240V** and `L/N`, so your unit should be treated as the AC version.

### 6.3 Sensor input terminals

The manual defines:
- `S+` = sensor signal +
- `S-` = sensor signal -
- `E+` = excitation +
- `E-` = excitation -

### 6.4 External digital input

Shorting the DI input can trigger a selectable remote function:
- temporary tare
- saved tare
- cancel tare
- temporary zero
- saved zero calibration
- clear peak  
This function is configured by menu parameter `109.di`.

### 6.5 Relay outputs

The manual states all outputs are **passive dry contacts**. The rear legend shows:
- `OUT1`: 3-terminal relay contact set
- `OUT2`: 3-terminal relay contact set
- `OUT3`: 2-terminal contact pair on the observed label

Because the PDF does not explicitly label `COM / NO / NC` in text, **verify contact state with a multimeter before wiring an external load**.

### 6.6 Analog output

Optional analog output supports:
- `0–20 mA`
- `4–20 mA`
- `4–12–20 mA`
- `0–3.3 V`
- `0–5 V`
- `0–10 V`
- `0–5–10 V`

### 6.7 RS485

Optional RS485 uses **Modbus-RTU** and supports:
- addressed communication,
- configurable baud / parity / stop bits,
- an “active send” mode,
- configured send frequencies up to `1000 Hz` per menu definition.

---

## 7. Quick-start workflow

1. **Install the unit mechanically** in the panel cutout.
2. **Wire power** according to the actual board version.
3. **Wire the sensor** to `E+ / E- / S+ / S-`.
4. **Power on** and verify the display exits the `PoiNt` startup state.
5. **Zero the system** with no load.
6. **Perform calibration**:
   - either with a real applied load (`Load` mode),
   - or by entering sensor sensitivity / range (`data` mode).
7. Configure optional:
   - relay outputs,
   - analog output,
   - RS485.
8. Validate:
   - zero,
   - tare,
   - span,
   - overload,
   - communications / output scaling.

---

## 8. Normal operating actions

## 8.1 Zero

### Purpose
Set the current no-load reading to zero.

### How to do it
1. Remove the load from the sensor.
2. Wait until the reading is stable.
3. Long-press the **Calibration/Down** key to enter the zero action.
4. Confirm if prompted.

### Constraints
- Zero will only be accepted if the current absolute reading is within the configured `405.Zr` zero range.
- If zero fails, you may see `AL.MZr`.

---

## 8.2 Tare

### Purpose
Subtract the current applied offset load so the displayed net value becomes zero.

### How to do it
1. Place the tare load on the sensor.
2. Wait until the reading is stable.
3. Long-press the **Up / Tare** key.
4. The display should switch to net-zero behavior.

### Clearing tare
Use either:
- the configured DI action `CPEEL`, or
- menu action / re-zero workflow depending on your setup.

### Constraints
- If tare conditions are not met, the instrument may show `AL.PEL`.

---

## 8.3 Cycle the secondary display

### Purpose
Change what the lower display shows.

### How to do it
1. In normal measurement mode, short-press **ENT**.
2. Cycle through:
   - unit,
   - gross,
   - peak.

The default secondary-display item is set by `104.ds`.

---

## 8.4 Peak display and clear peak

### Purpose
Capture and display peak value behavior.

### How to use
1. Enable / tune peak behavior using:
   - `110.MZ` peak threshold
   - `111.MN` peak detection interval
2. Use **ENT** to switch the secondary display to peak.
3. Long-press **ENT** to clear the stored peak value.

---

## 9. Menu structure overview

| Main menu | Purpose                       |
| --------- | ----------------------------- |
| `C1.SyS`  | System settings               |
| `C2.CAL`  | Calibration settings          |
| `C3.rEL`  | Relay output configuration    |
| `C4.AdV`  | Advanced application behavior |
| `C5.CoM`  | RS485 communication           |
| `C6.aNa`  | Analog output                 |
| `C7.LOC`  | Login password                |
| `C8.FAC`  | Factory calibration           |
| `C9.iNF`  | Version / device info         |

---

## 10. `C1.SyS` — System settings

| Code     | Name                      | Default | Range                     | Purpose / notes                                                   |
| -------- | ------------------------- | ------: | ------------------------- | ----------------------------------------------------------------- |
| `100.SP` | Sampling rate             |   `40H` | `10, 40, 640, 1280 Hz`    | Select acquisition/update speed                                   |
| `101.GA` | Gain adjustment           |  `128B` | `1, 2, 64, 128B`          | ADC gain selection                                                |
| `102.ME` | Median filtering          |     `5` | `1, 3, 5, 9`              | Median of N samples                                               |
| `103.rV` | Average filtering         |     `5` | `1–50`                    | Larger value = more stable, slower response                       |
| `104.ds` | Secondary display default |  `uNit` | `0:Gross, 1:Peak, 2:Unit` | Lower display default item                                        |
| `105.uN` | Unit selection            |    `kG` | `0–9`                     | `NoNE, g, kg, t, N, pa, kPa, MPa, N·m, kN`                        |
| `106.bi` | Decimal point position    |     `0` | `0–4`                     | Display format                                                    |
| `107.dV` | Graduation value          |     `1` | `1,2,5,10,20,50,100`      | Display increment / division                                      |
| `108.ro` | Maximum weighing          | `99999` | `0–99999`                 | Over this, display `AL.oL`; must be `≤ total sensor range - tare` |
| `109.di` | DI switch input function  |  `NoNE` | `0–6`                     | Remote DI behavior                                                |
| `110.MZ` | Peak judgment threshold   |    `50` | `0–50000`                 | Threshold to re-arm / refresh peak detection                      |
| `111.MN` | Peak detection interval   |   `0.5` | `0–5.000 s`               | Minimum interval between peak detections                          |
| `112.br` | Display brightness        |    `L5` | `L1–L8`                   | LED brightness                                                    |
| `113.uP` | Display refresh time      |  `0.02` | `0.02–1.000 s`            | How often displayed value refreshes                               |
| `114.bp` | Backup parameters         |    `NO` | `YES/NO`                  | Store current config and calibration                              |
| `115.Lp` | Load backup parameters    |    `NO` | `YES/NO`                  | Restore previously saved backup                                   |
| `116.FA` | Restore factory settings  |    `NO` | `YES/NO`                  | Factory default reset                                             |

### 10.1 How to configure system settings
1. Press **Fn** to enter the menu.
2. Use **Down** and **Up** to move/select parameters.
3. Press **ENT** to edit / confirm.
4. Use **Fn** to go back.

### 10.2 Recommended starting values
For a single load cell in a lab / bench environment:
- `100.SP = 40 Hz`
- `102.ME = 3 or 5`
- `103.rV = 5–10`
- `113.uP = 0.05–0.10 s`

For faster force events / peak capture:
- raise `100.SP` to `640` or `1280 Hz`
- reduce `103.rV`
- tune `110.MZ` and `111.MN`

---

## 11. `C2.CAL` — Calibration

| Code     | Name                          | Default | Range                  | Purpose                                                      |
| -------- | ----------------------------- | ------: | ---------------------- | ------------------------------------------------------------ |
| `200.ZE` | Zero calibration              |       — | AD internal code value | Save current zero point                                      |
| `201.Mo` | Calibration mode              |  `Load` | `Load / data`          | Choose physical-weight or digital-entry calibration          |
| `202.WE` | Weight value                  |       — | actual load            | Applied reference weight in `Load` mode                      |
| `203.rA` | Sensor range                  |       — | `10–99999`             | Single-sensor range × number of sensors; used in `data` mode |
| `204.SE` | Sensor sensitivity            | `2.000` | `0.010–10.000 mV/V`    | Enter sensor sensitivity                                     |
| `205.rE` | Sensor excitation voltage     |     `5` | `0.010–10.000 V`       | Excitation level                                             |
| `206.rV` | Range correction factor       | `1.000` | `0.010–2.000`          | Fine span correction                                         |
| `207.mE` | Multi-point correction enable |     `0` | `0:Close, 1:Open`      | Turn multipoint correction on/off                            |
| `208.mC` | Multipoint calibration        |       — | example-based          | Add correction points                                        |
| `209.Mr` | Calibration points            |       — | —                      | Number of multipoint-calibration points                      |

## 11.1 Recommended calibration workflow (load calibration)
This is the most practical method for your PM58 load cell.

1. Mechanically install the sensor.
2. Wire the sensor to `E+ / E- / S+ / S-`.
3. Let the system warm up for a few minutes.
4. Remove all applied load.
5. Enter `C2.CAL`.
6. Run `200.ZE` to save the zero point.
7. Ensure `201.Mo = Load`.
8. Set `202.WE` to the known calibration load you will apply.
9. Apply that known physical load.
10. Confirm the calibration operation when prompted by the UI.
11. Remove and re-apply the load to validate linearity.
12. If span is slightly off, adjust `206.rV`.
13. If needed, enable `207.mE` and use `208.mC` for multipoint correction.

## 11.2 Digital calibration (`data` mode)
Use this when the sensor datasheet is trusted and physical calibration weight is unavailable.

1. Enter `C2.CAL`.
2. Run `200.ZE` with no load.
3. Set `201.Mo = data`.
4. Set `203.rA = single-sensor full-scale × number of sensors`.
5. Set `204.SE = sensor sensitivity (mV/V)`.
6. Set `205.rE = excitation voltage` used by the indicator.
7. Confirm calibration.
8. Validate with one or more real loads anyway; if necessary trim with `206.rV`.

### Example for your PM58
Your PM58 certificate / label shows approximately:
- range: `100 kg`
- sensitivity: about `1.504 mV/V`
- excitation / supply range: `5–12 V`

Because this indicator excites the sensor at `5 V`, a digital calibration starting point would be:
- `203.rA = 100` (or `100000` if your chosen engineering-unit scale is in grams)
- `204.SE ≈ 1.504`
- `205.rE = 5.000`

> Final scaling depends on the unit and decimal-point choices under `C1.SyS`.

## 11.3 When calibration will fail
The instrument can reject calibration if data is unstable. The error code `Er.buy` explicitly says operations like zeroing / calibration may fail when the data has not become stable first.

---

## 12. `C3.rEL` — Relay outputs

Each relay can be configured independently.

| Code                           | Name                           | Meaning                               |
| ------------------------------ | ------------------------------ | ------------------------------------- |
| `300.m1` / `306.m2` / `312.m3` | Working mode                   | Relay behavior                        |
| `301.V1` / `307.V2` / `313.V3` | Data type                      | Which measured value drives the relay |
| `302.r1` / `308.r2` / `314.R3` | Return difference / hysteresis | Prevent chatter                       |
| `303.t1` / `309.t2` / `315.t3` | Action delay                   | Delay before relay actuation          |
| `304.h1` / `310.h2` / `316.h3` | Upper limit                    | High threshold                        |
| `305.L1` / `311.L2` / `317.L3` | Lower limit                    | Low threshold                         |

### 12.1 Relay working modes
| Value | Mode    | Purpose                        |
| ----- | ------- | ------------------------------ |
| `0`   | `NoNE`  | Disabled                       |
| `1`   | `hiGh`  | Activate above upper threshold |
| `2`   | `Low`   | Activate below lower threshold |
| `3`   | `iNraN` | Activate within band           |
| `4`   | `outrN` | Activate outside band          |

### 12.2 Relay data source
| Value | Data source |
| ----- | ----------- |
| `0`   | Gross       |
| `1`   | Net         |
| `2`   | Peak        |

### 12.3 Example: configure OUT1 as an over-force alarm
1. Enter `C3.rEL`.
2. Set `300.m1 = hiGh`.
3. Set `301.V1 = NEt` (or `GroSS`, depending on your use case).
4. Set `304.h1` to the alarm threshold.
5. Set `302.r1` to a hysteresis value to stop relay chatter.
6. Optionally set `303.t1` for delayed actuation.
7. Save and test.

### 12.4 Example: configure OUT2 as an in-window OK signal
1. Set `306.m2 = iNraN`.
2. Set `307.V2` to the desired data source.
3. Set `311.L2 = lower bound`.
4. Set `310.h2 = upper bound`.
5. Tune `308.r2` and `309.t2`.

---

## 13. `C4.AdV` — Advanced applications

| Code     | Name                             | Default | Range          | Purpose                                        |
| -------- | -------------------------------- | ------: | -------------- | ---------------------------------------------- |
| `400.CV` | Creep tracking                   |     `0` | `0–10`         | Compensate slow drift / creep                  |
| `401.dZ` | Display zeroing range            |     `0` | `0–50000`      | Display zero while internal value still exists |
| `402.tV` | Dynamic tracking range           |     `0` | `0–50000`      | Dynamic tracking behavior                      |
| `403.tC` | Dynamic tracking refresh         |   `0.2` | `0–2.000`      | Dynamic-tracking refresh interval              |
| `404.SV` | Stable weight switch             |     `0` | `0–1`          | Show only final stable value                   |
| `405.Zr` | Zero range                       |   `500` | `0–50000`      | Allowed manual / automatic zeroing range       |
| `406.PZ` | Power-on zero switch             |     `0` | `0–1`          | Enable auto-zero after power-up                |
| `407.Pt` | Power-on zero time               |    `10` | `0–1800 s`     | Countdown time after power-up                  |
| `408.Pr` | Power-on zero range              |    `50` | `0–50000`      | Allowed zero-detection band at startup         |
| `409.AZ` | Automatic zero switch            |     `0` | `0–1`          | Background auto-zero enable                    |
| `410.At` | Automatic zeroing time           |  `0.10` | `0.01–9.999 s` | Dwell time for auto-zero                       |
| `411.Ar` | Automatic zero range (divisions) |   `1.0` | `0.1–50.0`     | Auto-zero band in divisions                    |
| `412.Wr` | Stability range (divisions)      |     `0` | `0–5`          | Stable-window threshold                        |
| `413.Wt` | Stability time                   | `1.000` | `0.01–9.999 s` | Stable detection time                          |

### 13.1 Interpreting the advanced features

#### `400.CV` — creep tracking
Use to compensate slow offset drift in the measured value.  
- `0` = disabled  
- higher values = stronger tracking  

#### `401.dZ` — display zeroing range
If the absolute reading is within this range, the display shows zero **but the internal value is not actually reset**.  
Example from the manual:
- actual zero offset = `4`
- `401.dZ = 5`
- display shows `0`
- if you then apply `20`, the display becomes `24`

#### `404.SV` — stable weight switch
When enabled, the display jumps directly to the final stable value instead of visibly ramping through intermediate values.

#### `409.AZ`, `410.At`, `411.Ar`
This is the true **automatic zeroing** function. Unlike `401.dZ`, this one actually pulls the zero point back to zero after the reading stays inside the configured zero band for the configured time.

#### `412.Wr`, `413.Wt`
These define whether the instrument considers the weight **stable**. Stability matters because tare, zero, and calibration acceptance can depend on it.

### 13.2 Recommended starting values for force / bench testing
- `400.CV = 0` initially
- `401.dZ = 0` unless you intentionally want cosmetic zeroing
- `404.SV = 0` for live observation, `1` for operator-facing stable display
- `409.AZ = 0` for dynamic force tests
- `412.Wr = 1` or `2`
- `413.Wt = 0.2–1.0 s`

---

## 14. `C5.CoM` — RS485 communication

| Code     | Name                  | Default | Range   | Purpose                                  |
| -------- | --------------------- | ------: | ------- | ---------------------------------------- |
| `500.Ar` | Address               |     `1` | `1–253` | Modbus slave address                     |
| `501.br` | Baud rate             |     `3` | `1–15`  | Baud-rate selection                      |
| `502.Vb` | Check bit             |     `0` | `0–2`   | Parity                                   |
| `503.so` | Stop bit              |     `1` | `1/2`   | Stop-bit selection                       |
| `504.AS` | Active sending mode   |     `0` | `0–1`   | `0` = Modbus RTU mode, `1` = active send |
| `505.AF` | Active-send frequency |     `2` | `0–9`   | `1 Hz` to `1000 Hz`                      |

### 14.1 Baud-rate codes
| Code | Baud rate |
| ---- | --------: |
| `1`  |    `2400` |
| `2`  |    `4800` |
| `3`  |    `9600` |
| `4`  |   `19200` |
| `5`  |   `22800` |
| `6`  |   `38400` |
| `7`  |   `57600` |
| `8`  |  `115200` |
| `9`  |  `128000` |
| `10` |  `230400` |
| `11` |  `256000` |
| `12` |  `460800` |
| `13` |  `500000` |
| `14` |  `512000` |
| `15` |  `600000` |

   2400,   4800,   9600,  19200,  22800,  38400,  57600, 115200, 128000, 230400, 256000, 460800, 500000, 512000, 600000,

### 14.2 Parity codes
| Code | Meaning |
| ---- | ------- |
| `0`  | none    |
| `1`  | even    |
| `2`  | odd     |

### 14.3 Important UI note
The PDF says baud-rate changes apply immediately, but because the display is short, the UI omits the last two digits when showing the value.  
Examples:
- `2400` may display as `24`
- `115200` may display as `1152`

### 14.4 How to enable Modbus RTU
1. Enter `C5.CoM`.
2. Set `500.Ar` to the device address.
3. Set `501.br`, `502.Vb`, `503.so` to match the host.
4. Set `504.AS = 0` (this means **Modbus RTU**, not active-send mode).
5. Power-cycle / reconnect the host if needed.

### 14.5 How to enable active-send mode
1. Enter `C5.CoM`.
2. Set serial format parameters as needed.
3. Set `504.AS = 1`.
4. Set `505.AF` to the desired push frequency.
5. Validate on the host with a serial capture.

> The PDF confirms that `504.AS = 0` means Modbus-RTU mode, but it does not document the active-send payload format.

---

## 15. `C6.aNa` — Analog output

| Code     | Name                       | Default | Range         | Purpose                      |
| -------- | -------------------------- | ------: | ------------- | ---------------------------- |
| `600.At` | AO output type             |     `1` | `0–3`         | What signal drives AO        |
| `601.As` | AO signal type             |     `0` | `0–1`         | Current or voltage           |
| `602.ax` | AO maximum weight          |  `5000` | `0–99999`     | Full-scale mapped value      |
| `603.ai` | AO minimum weight          |     `0` | `0–9999`      | Zero-point mapped value      |
| `604.aP` | AO minimum-weight polarity |     `0` | `0–1`         | Positive or negative minimum |
| `605.CL` | Lower current limit        |     `4` | `0–10.00`     | Usually `0` or `4 mA`        |
| `606.Ch` | Upper current limit        |    `20` | `10.00–21.00` | Usually `20 mA`              |
| `607.VL` | Lower voltage limit        |     `0` | `0–5.00`      | Usually `0 V`                |
| `608.Vh` | Upper voltage limit        | `10.00` | `5.00–10.00`  | Usually `5 V` or `10 V`      |

### 15.1 AO source selection
| `600.At` value | Source |
| -------------- | ------ |
| `0`            | None   |
| `1`            | Gross  |
| `2`            | Net    |
| `3`            | Peak   |

### 15.2 AO signal type
| `601.As` value | Type    |
| -------------- | ------- |
| `0`            | Current |
| `1`            | Voltage |

### 15.3 Supported analog-output modes
The PDF implies the following are obtained by setting the limits appropriately:

#### Current mode
- `0–20 mA` → `605.CL = 0`, `606.Ch = 20`
- `4–20 mA` → `605.CL = 4`, `606.Ch = 20`
- `4–12–20 mA` → use negative minimum polarity and bipolar span arrangement

#### Voltage mode
- `0–5 V` → `607.VL = 0`, `608.Vh = 5`
- `0–10 V` → `607.VL = 0`, `608.Vh = 10`
- `0–5–10 V` → use negative minimum polarity and bipolar span arrangement

### 15.4 How to configure 4–20 mA output
1. Enter `C6.aNa`.
2. Set `600.At` = desired source (`Gross`, `Net`, or `Peak`).
3. Set `601.As = Curr`.
4. Set `603.ai` = minimum engineering value.
5. Set `602.ax` = maximum engineering value.
6. Set `604.aP = plus`.
7. Set `605.CL = 4`.
8. Set `606.Ch = 20`.
9. Measure the output with a meter and validate.

### 15.5 How to configure 0–10 V output
1. Set `600.At` to desired source.
2. Set `601.As = VoLt`.
3. Set `603.ai` = minimum engineering value.
4. Set `602.ax` = maximum engineering value.
5. Set `604.aP = plus`.
6. Set `607.VL = 0`.
7. Set `608.Vh = 10`.
8. Validate using a voltmeter or analog-input card.

### 15.6 Bipolar note
The manual explicitly says that when `604.aP = miNus`, the AO minimum corresponds to a **negative full-scale direction**, enabling midpoint-style output modes such as:
- `4–12–20 mA`
- `0–5–10 V`

---

## 16. `C7.LOC` — Password control

| Code     | Name            | Default | Range    | Purpose                           |
| -------- | --------------- | ------: | -------- | --------------------------------- |
| `700.oP` | Password switch |     `0` | `0–1`    | Enable / disable login protection |
| `701.PW` | Change password |  `0000` | `0–9999` | User password                     |

### How to use
1. Set `700.oP = Open` to require password entry.
2. Use `701.PW` to set a new password.
3. The manual says the existing password must be entered before a new one can be stored.

---

## 17. `C8.FAC` — Factory calibration (reserved)

| Code     | Name                     | Purpose                    |
| -------- | ------------------------ | -------------------------- |
| `800.Lo` | Manufacturer password    | Internal factory access    |
| `801.EX` | Exit factory calibration | Leave factory menu         |
| `802.01` | AO 0.1 mA calibration    | Factory analog calibration |
| `803.4m` | AO 4 mA calibration      | Factory analog calibration |
| `804.1O` | AO 10 mA calibration     | Factory analog calibration |
| `805.12` | AO 12 mA calibration     | Factory analog calibration |
| `806.20` | AO 20 mA calibration     | Factory analog calibration |
| `807.UU` | AO 10 V calibration      | Factory analog calibration |
| `808.Ad` | ADC benchmark setting    | Factory ADC trim           |

### Recommendation
Do **not** modify `C8.FAC` unless you are intentionally recalibrating the analog-output stage and have traceable measurement equipment.

---

## 18. `C9.iNF` — Version / identification

| Code     | Name                    | Purpose           |
| -------- | ----------------------- | ----------------- |
| `900.VE` | Software version number | Firmware version  |
| `901.id` | Unique device code      | Device identifier |

---

## 19. External DI / remote-trigger behavior

The manual says shorting terminals `3` and `4` can perform a configurable remote action.  
This is chosen by `109.di`:

| Value | Function                                   |
| ----- | ------------------------------------------ |
| `0`   | None                                       |
| `1`   | `tPEEL` — tare, not saved after power loss |
| `2`   | `SPEEL` — tare, saved after power loss     |
| `3`   | `CPEEL` — cancel tare, saved               |
| `4`   | `SZEro` — zero, not saved after power loss |
| `5`   | `CZEro` — zero calibration, saved          |
| `6`   | `REMAX` — clear peak                       |

### How to use
1. Set `109.di` to the desired action.
2. Wire a dry contact or switch to `DI+` / `DI-`.
3. Briefly short the input to trigger the action.
4. Confirm behavior before deploying in production.

---

## 20. Faults and status messages

### 20.1 Secondary-display messages

| Code     | Meaning                                                                                            |
| -------- | -------------------------------------------------------------------------------------------------- |
| `PoiNt`  | Power-on initialization; exits after first valid data, or after power-on-zero countdown if enabled |
| `-----`  | No valid peak has been captured                                                                    |
| `Err.ro` | EEPROM read/write failure                                                                          |
| `Err.Ad` | ADC fault                                                                                          |
| `AL.Ad`  | ADC overrange / signal too large / max-min ADC code reached                                        |
| `AL.oL`  | Sensor overload or exceeds configured max range                                                    |
| `AL.AZR` | Power-on zero failed; outside configured startup zero range                                        |
| `AL.PEL` | Manual tare failed; tare conditions not satisfied                                                  |
| `AL.MZr` | Manual zero failed; zero conditions not satisfied                                                  |

### 20.2 Main-display messages

| Code     | Meaning                                                     |
| -------- | ----------------------------------------------------------- |
| `-----`  | Appears while modifying sampling rate; auto-exits           |
| `Er.doM` | Entered value too small; clamped to minimum                 |
| `Er.up`  | Entered value too large; clamped to maximum                 |
| `Er.iNV` | Invalid user input                                          |
| `Er.pwE` | Wrong password                                              |
| `FA.roM` | Parameter write failed, but values already took effect      |
| `FA.AdC` | ADC setting failed                                          |
| `Er.buy` | Instrument busy; operation attempted before data was stable |

### Troubleshooting guidance
- `AL.Ad` → check sensor wiring, overload, broken cable, wrong excitation/signal wiring, sensor out of range.
- `AL.oL` → reduce load or increase configured max range `108.ro`.
- `AL.AZR` → widen `408.Pr` or fix startup offset.
- `AL.PEL`, `AL.MZr`, `Er.buy` → wait for stability; review `412.Wr` / `413.Wt`, filtering, and mechanical vibration.

---

## 21. Practical configuration recipes

## 21.1 Stable bench scale setup
- `100.SP = 40`
- `102.ME = 5`
- `103.rV = 10`
- `404.SV = 0`
- `409.AZ = 1`
- `410.At = 0.2`
- `411.Ar = 1.0`
- `412.Wr = 1`
- `413.Wt = 0.5`

## 21.2 Fast force / peak capture setup
- `100.SP = 640` or `1280`
- `102.ME = 1` or `3`
- `103.rV = 1–3`
- `110.MZ` = application-dependent
- `111.MN` = small nonzero interval
- `404.SV = 0`
- `409.AZ = 0`

## 21.3 PLC analog-output setup (4–20 mA)
- `600.At = NEt`
- `601.As = Curr`
- `603.ai = minimum process value`
- `602.ax = maximum process value`
- `605.CL = 4`
- `606.Ch = 20`

## 21.4 PLC RS485 / Modbus setup
- `500.Ar = chosen slave address`
- `501.br = 9600` or `115200`
- `502.Vb = none`
- `503.so = 1`
- `504.AS = 0`

---

## 22. Operating notes on ambiguous terms

The source PDF is machine-translated and some terms are unclear. This rewrite uses the following interpretations:

| Source term                | Recommended interpretation                             |
| -------------------------- | ------------------------------------------------------ |
| “peeling”                  | tare                                                   |
| “zero point calibration”   | persistent zero calibration                            |
| “display zeroing”          | cosmetic zero display without resetting internal value |
| “dynamic tracking”         | dynamic drift / motion tracking behavior               |
| “stable weight switch”     | show only final stable value                           |
| “return difference”        | hysteresis                                             |
| “mailing address”          | communication / Modbus address                         |
| “load ballast calibration” | real applied-weight calibration                        |
| “data digital calibration” | digital-entry calibration using sensor specs           |

---

## 23. Modbus register map

The PDF provides a master/slave Modbus-RTU register map. The table below ports the documented content into a more readable form.

### 23.1 Read-only measurement values

|  Dec | Hex      |   PLC | Name                    | Type               | Access | Notes                |
| ---: | -------- | ----: | ----------------------- | ------------------ | ------ | -------------------- |
|    0 | `0x0000` | 40001 | Total weight low word   | 32-bit signed low  | R      | Gross / total weight |
|    1 | `0x0001` | 40002 | Total weight high word  | 32-bit signed high | R      | Gross / total weight |
|    2 | `0x0002` | 40003 | Net weight low word     | 32-bit signed low  | R      | Net weight           |
|    3 | `0x0003` | 40004 | Net weight high word    | 32-bit signed high | R      | Net weight           |
|    4 | `0x0004` | 40005 | Peak value low word     | 32-bit signed low  | R      | Peak                 |
|    5 | `0x0005` | 40006 | Peak value high word    | 32-bit signed high | R      | Peak                 |
|    6 | `0x0006` | 40007 | Internal code low word  | 32-bit signed low  | R      | ADC internal code    |
|    7 | `0x0007` | 40008 | Internal code high word | 32-bit signed high | R      | ADC internal code    |

### 23.2 Shared configuration / status registers

|  Dec | Hex      |   PLC | Name                         | Type               | Access | Meaning                                                                                                                         |
| ---: | -------- | ----: | ---------------------------- | ------------------ | ------ | ------------------------------------------------------------------------------------------------------------------------------- |
|    8 | `0x0008` | 40009 | Decimal point                | 16-bit unsigned    | R/W    | `0:00000`, `1:0000.0`, `2:000.00`, `3:00.000`, `4:0.0000`                                                                       |
|    9 | `0x0009` | 40010 | Unit                         | 16-bit unsigned    | R/W    | `0:none`, `1:g`, `2:kg`, `3:t`, `4:N`, `5:pa`, `6:kPa`, `7:MPa`, `8:N·m`, `9:kN`                                                |
|   10 | `0x000A` | 40011 | Status                       | 16-bit unsigned    | R      | bit / code-like status item list per manual                                                                                     |
|   11 | `0x000B` | 40012 | Command                      | 16-bit unsigned    | R/W    | `1:tare temp`, `2:tare save`, `3:cancel tare`, `4:zero temp`, `5:zero save`, `6:clear peak`, `7:calibration`, `9:factory reset` |
|   12 | `0x000C` | 40013 | Weight value low word        | 32-bit signed low  | R/W    | calibration weight input                                                                                                        |
|   13 | `0x000D` | 40014 | Weight value high word       | 32-bit signed high | R/W    | calibration weight input                                                                                                        |
|   14 | `0x000E` | 40015 | Creep tracking               | 16-bit unsigned    | R/W    | `0–10`                                                                                                                          |
|   15 | `0x000F` | 40016 | Display zeroing              | 16-bit unsigned    | R/W    | `0–5000`                                                                                                                        |
|   16 | `0x0010` | 40017 | Dynamic tracking range       | 16-bit unsigned    | R/W    | `0–5000`                                                                                                                        |
|   17 | `0x0011` | 40018 | Dynamic tracking update time | 16-bit unsigned    | R/W    | `0–2000 ms`                                                                                                                     |
|   18 | `0x0012` | 40019 | Stable weight switch         | 16-bit unsigned    | R/W    | `0:off`, `1:on`                                                                                                                 |
|   19 | `0x0013` | 40020 | Zero range                   | 16-bit unsigned    | R/W    | `0–5000`                                                                                                                        |
|   20 | `0x0014` | 40021 | Power-on zero enable         | 16-bit unsigned    | R/W    | `0:off`, `1:on`                                                                                                                 |
|   21 | `0x0015` | 40022 | Power-on zero time           | 16-bit unsigned    | R/W    | `0–1800 s`                                                                                                                      |
|   22 | `0x0016` | 40023 | Power-on zero range          | 16-bit unsigned    | R/W    | `0–50000`                                                                                                                       |
|   23 | `0x0017` | 40024 | Automatic zero enable        | 16-bit unsigned    | R/W    | `0:off`, `1:on`                                                                                                                 |
|   24 | `0x0018` | 40025 | Automatic zeroing time       | 16-bit unsigned    | R/W    | `100–9999 ms`                                                                                                                   |
|   25 | `0x0019` | 40026 | Automatic zero range         | 16-bit unsigned    | R/W    | `10–500` in 0.1-division units                                                                                                  |
|   26 | `0x001A` | 40027 | Stable range division        | 16-bit unsigned    | R/W    | `0–5`                                                                                                                           |
|   27 | `0x001B` | 40028 | Stable time                  | 16-bit unsigned    | R/W    | `100–9999 ms`                                                                                                                   |

### 23.3 Relay 1 registers

|  Dec | Hex      |   PLC | Name                          | Type                 | Access |
| ---: | -------- | ----: | ----------------------------- | -------------------- | ------ |
|   28 | `0x001C` | 40029 | Relay 1 working mode          | 16-bit unsigned      | R/W    |
|   29 | `0x001D` | 40030 | Relay 1 hysteresis            | 16-bit unsigned      | R/W    |
|   30 | `0x001E` | 40031 | Relay 1 data type             | 16-bit unsigned      | R/W    |
|   31 | `0x001F` | 40032 | Relay 1 action delay          | 16-bit unsigned      | R/W    |
|   32 | `0x0020` | 40033 | Relay 1 upper limit low word  | 16-bit unsigned low  | R/W    |
|   33 | `0x0021` | 40034 | Relay 1 upper limit high word | 16-bit unsigned high | R/W    |
|   34 | `0x0022` | 40035 | Relay 1 lower limit low word  | 16-bit unsigned low  | R/W    |
|   35 | `0x0023` | 40036 | Relay 1 lower limit high word | 16-bit unsigned high | R/W    |

### 23.4 Relay 2 registers

|  Dec | Hex      |   PLC | Name                          | Type                 | Access |
| ---: | -------- | ----: | ----------------------------- | -------------------- | ------ |
|   36 | `0x0024` | 40037 | Relay 2 working mode          | 16-bit unsigned      | R/W    |
|   37 | `0x0025` | 40038 | Relay 2 hysteresis            | 16-bit unsigned      | R/W    |
|   38 | `0x0026` | 40039 | Relay 2 data type             | 16-bit unsigned      | R/W    |
|   39 | `0x0027` | 40040 | Relay 2 action delay          | 16-bit unsigned      | R/W    |
|   40 | `0x0028` | 40041 | Relay 2 upper limit low word  | 16-bit unsigned low  | R/W    |
|   41 | `0x0029` | 40042 | Relay 2 upper limit high word | 16-bit unsigned high | R/W    |
|   42 | `0x002A` | 40043 | Relay 2 lower limit low word  | 16-bit unsigned low  | R/W    |
|   43 | `0x002B` | 40044 | Relay 2 lower limit high word | 16-bit unsigned high | R/W    |

### 23.5 Relay 3 registers

|  Dec | Hex      |   PLC | Name                          | Type                 | Access |
| ---: | -------- | ----: | ----------------------------- | -------------------- | ------ |
|   44 | `0x002C` | 40045 | Relay 3 working mode          | 16-bit unsigned      | R/W    |
|   45 | `0x002D` | 40046 | Relay 3 hysteresis            | 16-bit unsigned      | R/W    |
|   46 | `0x002E` | 40047 | Relay 3 data type             | 16-bit unsigned      | R/W    |
|   47 | `0x002F` | 40048 | Relay 3 action delay          | 16-bit unsigned      | R/W    |
|   48 | `0x0030` | 40049 | Relay 3 upper limit low word  | 16-bit unsigned low  | R/W    |
|   49 | `0x0031` | 40050 | Relay 3 upper limit high word | 16-bit unsigned high | R/W    |
|   50 | `0x0032` | 40051 | Relay 3 lower limit low word  | 16-bit unsigned low  | R/W    |
|   51 | `0x0033` | 40052 | Relay 3 lower limit high word | 16-bit unsigned high | R/W    |

---

## 24. Validation and commissioning checklist

### Electrical
- [ ] Correct board version identified (AC vs DC)
- [ ] Sensor wired to `E+ E- S+ S-`
- [ ] No sensor / RS485 / AO line accidentally tied to mains
- [ ] Cabinet grounding handled externally

### Functional
- [ ] Unit powers on and exits `PoiNt`
- [ ] Zero works with no load
- [ ] Tare works with preload
- [ ] Span / calibration checked with known mass or force
- [ ] Overload behavior checked
- [ ] Peak capture behavior checked

### Outputs
- [ ] Relay thresholds tested
- [ ] AO scaling validated with meter / PLC card
- [ ] RS485 readback validated
- [ ] DI trigger behavior validated

---

## 25. What this rewrite changes versus the PDF

This Markdown keeps the PDF content but improves it by:
1. grouping settings by function,
2. translating “peeling” into tare semantics,
3. separating cosmetic zeroing from true zero calibration,
4. turning scattered parameter definitions into usable procedures,
5. surfacing the practical differences between:
   - zero,
   - tare,
   - startup zero,
   - automatic zero,
   - display-zero range,
   - peak threshold / interval,
   - relay source / relay mode / hysteresis,
   - Modbus mode vs active-send mode,
   - analog source vs analog electrical format.

---

## 26. Source provenance

### Primary sources
1. Uploaded machine-translated PDF manual for the board.
2. Uploaded photos of the front panel and rear terminal label.
3. Uploaded PM58 load-cell certificate / label.

### Public web sources used for validation / corroboration
1. Public duplicate of the same manual hosted on AliExpress CDN.
2. Similar Chinese weighing-transmitter / force-indicator manuals used only to clarify:
   - A/D rate interpretation,
   - filter tradeoffs,
   - stable-detection gating of calibration / zero functions.

### Important caution
Where this Markdown provides step-by-step procedures that were **not explicitly spelled out** in the source PDF, those procedures are best-effort reconstructions based on:
- the menu definitions,
- the key legends,
- common behavior of comparable weighing indicators.

Use them as a practical commissioning guide, but validate on the real device during setup.

---
