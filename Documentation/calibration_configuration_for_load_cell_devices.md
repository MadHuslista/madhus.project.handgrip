# Calibration Configuration Report: Reference Acquisition Board vs. Target Sensor

## Overview

To achieve the best possible calibration of the target HX711 device against the **100Kg** reference acquisition board, the primary engineering challenge is **time-series synchronization**. 

Because the target device has a jittery, inconsistent sampling rate (~**93Hz** ± **15ms**), standard point-by-point calibration is impossible without a highly stable, high-resolution temporal baseline to interpolate against. Therefore, the reference device must be configured for low-latency, high-frequency, deterministic data pushing with minimal phase delay (filtering). 

By leveraging the reference board's "Active Send" Modbus feature and pushing both streams into a Lab Streaming Layer (LSL) environment, we can rely on LSL's host timestamping alongside the Arduino's microsecond timestamps (`<timestamp_us>`) to temporally align the jittery target data with the stable reference curve.

---

## Configuration Summary

| Device / Interface  | Parameter                 | Recommended Value             | Rationale                                                                                                                         |
| :------------------ | :------------------------ | :---------------------------- | :-------------------------------------------------------------------------------------------------------------------------------- |
| **Reference Board** | `100.SP` (Sampling Rate)  | **640 Hz**                    | High enough to provide a dense time-series for interpolating the **93Hz** target, without the excessive noise of **1280Hz**.      |
| **Reference Board** | `102.ME` (Median Filter)  | **3**                         | Minimal median filtering to reject pure noise spikes without introducing significant phase delay.                                 |
| **Reference Board** | `103.rV` (Average Filter) | **1** or **2**                | Very light averaging to smooth the signal while preserving the true temporal curve of the physical force.                         |
| **Reference Board** | `504.AS` (Active Send)    | **1 (Open/On)**               | Forces the board to push data autonomously, eliminating USB/OS polling jitter.                                                    |
| **Reference Board** | `505.AF` (Active Freq.)   | **8 (500 Hz)**                | Provides a stable **500 Hz** data stream to the PC, perfectly complementing the **640 Hz** internal sampling.                     |
| **Reference Board** | `501.br` (Baud Rate)      | **12 (460800)**               | High bandwidth is required to prevent buffer bottlenecks when streaming Modbus packets at **500 Hz**.                             |
| **Target Device**   | UART Baud Rate            | **115200**                    | Sufficient for pushing the `<timestamp_us>` payload at ~**93Hz**; maintains current Arduino stability.                            |
| **Host PC**         | Data Ingestion            | **LSL (Lab Streaming Layer)** | Solves the ~**93Hz** ± **15ms** jitter by applying unified, high-precision timestamps to both incoming data streams upon arrival. |

---

## Detailed Parameter Breakdown

### 1. Reference Sampling Rate (`100.SP`)
* **Recommended Value:** `640 Hz` (Menu option: `640`)
* **Overall Reason:** Hand grip force is a relatively slow biomechanical action (containing frequency content almost entirely below **10-15 Hz**). Setting the internal ADC sampling to **640 Hz** satisfies the Nyquist theorem by orders of magnitude while providing a dense array of data points.
* **Calibration Impact:** A dense **640 Hz** signal allows you to smoothly interpolate the reference force at the exact microsecond the **93 Hz** target device registers a sample.
* **Alternatives Rejected:** * *10 Hz / 40 Hz:* Too slow. If the reference updates slower than the target (**93Hz**), you will get stepped (staircase) data, making dynamic calibration impossible. 
    * *1280 Hz:* Unnecessary for human biomechanics. It introduces higher electronic noise, decreasing the signal-to-noise ratio (SNR) of your baseline truth.

### 2. Modbus Active Sending Mode (`504.AS`)
* **Recommended Value:** `1` (Active Send Enabled)
* **Overall Reason:** Traditional Modbus RTU is a passive, poll-and-response protocol. If your Linux PC polls the device over USB, the OS scheduler and USB polling rates will introduce massive software jitter. Active mode decouples this, allowing the board to proactively stream data to the PC on a strict hardware timer.
* **Calibration Impact:** Eliminates unpredictable delays in the reference data. You get a steady, deterministic timeline to compare against your inherently jittery Arduino.
* **Alternatives Rejected:** * *0 (Modbus RTU Polling):* Rejected because relying on a Python/C++ script to request data hundreds of times a second over USB-RS485 will result in missed frames, timeouts, and corrupted time synchronization.

### 3. Active Send Frequency (`505.AF`)
* **Recommended Value:** `8` (500 Hz)
* **Overall Reason:** This dictates how often the RS485 bus physically transmits a packet. **500 Hz** is over 5 times faster than your target device's ~**93Hz** rate, ensuring you have multiple reference "truth" points bridging every single Arduino sample.
* **Calibration Impact:** Guarantees that the maximum time gap between reference data points is **2 ms**, making linear interpolation against the target's timestamps nearly flawless.
* **Alternatives Rejected:** * *1000 Hz:* Pushing at **1000 Hz** when sampling at **640 Hz** means the board will send duplicate ADC readings. It wastes bandwidth without adding new physical data.
    * *100 Hz:* Too close to the target's ~**93 Hz** rate, which could introduce beating/aliasing artifacts during time-alignment.

### 4. RS485 Baud Rate (`501.br`)
* **Recommended Value:** `12` (460800 baud)
* **Overall Reason:** To send Modbus frames **500** times a second, you are pushing significant data volume. Including start/stop bits and wire overhead, a **115200** baud connection is dangerously close to saturation. **460800** baud clears the bus rapidly.
* **Calibration Impact:** Prevents UART buffer overruns and ensures the hardware packet latency is as close to zero as possible.
* **Alternatives Rejected:** * *115200 (Code 8):* Rejected due to the risk of bus saturation at **500 Hz** active sending.
    * *600000 (Code 15):* Rejected because non-standard baud rates often cause clock-divider issues on standard PC USB-to-RS485 adapters, leading to framing errors. **460800** is a standard high-speed multiple.

### 5. Digital Filtering (`102.ME` & `103.rV`)
* **Recommended Value:** `102.ME` = 3, `103.rV` = 1 or 2
* **Overall Reason:** Any digital filter inherently introduces a phase delay (time lag). The manual explicitly warns that larger average filter values cause a slower response. If you heavily filter the reference, its recorded force will lag behind the target device's recorded force in time, ruining the calibration map.
* **Calibration Impact:** By keeping the Median filter at **3** (to kill sudden EMI spikes) and Average filter at **1** or **2** (minimal smoothing), the reference signal stays temporally aligned with the physical event.
* **Alternatives Rejected:** * *High Average Filtering (e.g., 10-50):* Rejected. While it creates a highly stable number on the physical LED display, the data stream arriving at the PC will lag reality by tens or hundreds of milliseconds.

### 6. Target Device UART & LSL Integration
* **Recommended Value:** Keep UART at **115200**, utilize `<timestamp_us>` in LSL.
* **Overall Reason:** The target's UART payload (`D,<seq>,<timestamp_us>,<value>\n`) is roughly 30 characters. At **115200** baud, this takes less than **3 ms** to transmit, easily supporting the ~**93Hz** rate without bottlenecking.
* **Calibration Impact:** The HX711 is notoriously inconsistent, causing your observed `93Hz ± 15ms` jitter. By pushing both the Arduino stream and the RS485 Reference stream into LSL immediately upon arriving at the PC buffer, you can align the Arduino's `<timestamp_us>` against LSL's master clock. You can then write a calibration script that interpolates the **500Hz** reference data exactly at the timestamps where the **93Hz** target data arrived, enabling highly accurate curve-fitting (e.g., linear regression or polynomial mapping) between the two load cells.
* **Alternatives Rejected:**
    * *Lowering Target Baud Rate:* Rejected because it would artificially inflate the transmission latency, misaligning the `<timestamp_us>` with the actual physical event upon receipt.