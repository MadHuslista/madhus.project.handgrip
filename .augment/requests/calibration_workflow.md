# Context

Please review the current state of the Handgrip_Firmware, LSL_Bridge, LSL_Viewer and the RS485_GUI, and the Handgrip_Calibreation. The first 3 components works together to reads and provides a data streams to the host PC, the LSL_Bridge provides a live view of the data streams, and the Handgrip_Calibration executes the calibration workflows based on the data streams.
- The `Handgrip_Firmware` is the main firmware that runs on the Arduino Nano. It reads the load cell sensor data on the Arduino via the HX711, packs it into a unified format including data and internal timestamp, and sends it to the serial port using UART.
- The `RS485_GUI` is the Python application that reads the data from Acquisition Board via RS485 in either **Modbus RTU** (polling) or **Active-Send** (push) modes, typically at 500Hz, and shows it in a live plot, and also sends it via IPC to the `LSL_Bridge` 
- The `LSL_Bridge` is the Python application in charge to standardize the data streams into two LSL streams: one for the Handgrip_Firmware and one for the RS485_GUI. 
  - For the The Handgrip_Firmware stream, it applies a filtering preprocessing and then writes the data to the LSL stream as three channels: raw, filtered and clock. The sampling rate of this stream is unconsistent but averages to 93~100Hz.  
  - For the RS485_GUI stream it reads the IPC packages and writes the data to the LSL stream as two channels: raw and clock. The sampling rate of this stream is theoretically set by the acquisition board configured as `Modbus Active-Send` mode at 500Hz. In practice, reaches `498-500Hz`.

- The `LSL_Viewer` is a Python application that reads the 2 LSL streams and displays them in live time-series plots for each independent stream and two correlation plots that sync both signals and show it's correlation as an overlaped time-series plot and as a sensor-curve plot where the acquisition board is set as the reference on the x-axis and the Handgrip_Firmware is set as the target on the y-axis.

- The `Handgrip_Calibration` is a Python application that reads the data streams from the Handgrip_Firmware and the Acquisition Board, and executes the calibration workflows based on the data streams.

The purpose of all this components is to provide standardized data streams to the host PC that would allow to calibrate the Handgrip_Firmware based on the reference provided by the acquisition board.

## Measurement setup

For the calibration, a constant force can be applied across the handgrip's sensor and the acquisition board's sensor, both of which are conected in series in order that the force is shared between both sensors, and so the acquisition board measurement can be used as a reference for the Handgrip_Firmware calibration.

# Goal 

Design a set of calibration workflows to apply over the measurement setup described above, in order to generate enough data that would enable the handgrip device calibration based on the reference data provided by the acquisition board.

# Task

Based on the current state of the Handgrip_Firmware, LSL_Bridge and the RS485_GUI, and the documentation available in the project files, please design a set of detailed workflows to calibrate the handgrip device based on the reference provided by the acquisition board.

IMPORTANT: For that purpose, review on the web about relevant literature for calibration workflows. 

Base all the workflows on the highest epistemic quality possible, and include at least the following stages:
1. How to setup both devices (is expected that both sensors will be configured in series, and a constant regulable force will be applied across both sensors, so that the force is shared between both sensors). 
2. The force workflows recommended (type: {zero, constant, linear, ladder, ramp, etc}, ranges, speeds, etc), and in which order to apply them.
3. Which data to expect from, and how to analyze it. 
4. Once the calibration is done, how to measure the accuracy of the calibration.
5. How to iterate the calibration process and how to compare it's performance with previous calibrations.
6. Other relevant stages. 
The proposed stages should be reviewed, re-organized (meaning reorder, splitting and merging, refinded and others.) and updated based on the current state of the Handgrip_Firmware, LSL_Bridge and the RS485_GUI, and what's recommended by the relevant recollected information from the web. 

The workflow should be detailed enough to be able to use it as an instruction manual for the user, for the calibration process of the handgrip device.

----------------

# Task

Based on the current architecture of the `Handgrip_Firmware` (D2 payload), `LSL_Bridge` (v2 schema), and the `Handgrip_Calibration` module, design a comprehensive technical manual and workflow for calibrating the handgrip device using the RS485 acquisition board as a reference. 

Your design must integrate the existing configuration schemas found in `ProtocolConfig` and `FitConfig` and provide a high-epistemic-quality procedure covering the following stages:

1. **Physical Setup & Preflight**: Detail the mechanical requirements for connecting the HX711 target sensor and the PM58 reference sensor in series. Include instructions for verifying stream integrity using `handgrip-cal preflight --config conf/default.yaml` to ensure `HandgripTarget` (~100Hz) and `HandgripReference` (500Hz) are active.
2. **Calibration Protocol (Static Staircase)**: Define a "static-staircase" workflow based on `protocol_static_staircase.yaml`. Specify the order of operations: 
    - **Baseline**: 10s zero-force capture.
    - **Preload**: 3 cycles at 100N to minimize mechanical hysteresis.
    - **Staircase**: Ascending and descending holds (e.g., [0, 20, 40, 60, 80, 100, 80... 0] N) with 5s durations and 3s stability windows.
    - **Dynamic Validation**: Slow ramps and fast squeezes for post-fit verification.
3. **Data Acquisition & Analysis**: Explain the recording process using `handgrip-cal record`. Describe how the system reduces 500Hz reference data to match ~100Hz target timestamps and how it segments "accepted holds" based on `QualityConfig` thresholds (e.g., `max_hold_reference_std_N: 0.5`).
4. **Model Fitting & Accuracy**: Detail the affine fitting process (`force = a * raw + b`). Define the criteria for a "successful" calibration, specifically checking if residuals are within the `residual_threshold_percent_operating_range` (0.5% of 100N).
5. **Validation & Iteration**: Instruct the user on how to use the `dynamic_validation` data to test the fit. Provide a method for comparing `fit_result.json` across sessions to track sensor drift or performance changes.
6. **Reporting**: Describe the interpretation of the `calibration_report.html` and the generated correlation plots (sensor-curve and time-series overlays).

Ensure the workflow is formatted as a step-by-step instruction manual, referencing specific CLI commands and configuration parameters from the `Handgrip_Calibration` package.



-------------
# Context

Please review the provided latest state of the Handgrip_Firmware, LSL_Bridge, LSL_Viewer and the RS485_GUI, and the Handgrip_Calibration provided in the .zip files. 

The first 3 components works together to reads and provides a data streams to the host PC. 
The LSL_Viewer provides a live view of the data streams, and 
The Handgrip_Calibration executes the calibration protocol based on the data streams.

In more details, the components are:
- The `Handgrip_Firmware` is the main firmware that runs on the Arduino Nano. It reads the load cell sensor data on the Arduino via the HX711, packs it into a unified format including data and internal timestamp, and sends it to the serial port using UART.
- The `RS485_GUI` is the Python application that reads the data from Acquisition Board via RS485 in either **Modbus RTU** (polling) or **Active-Send** (push) modes, typically at 500Hz, and shows it in a live plot, and also sends it via IPC to the `LSL_Bridge` 
- The `LSL_Bridge` The central ingestion point that standardizes data into three LSL streams:
  - `HandgripTarget`: it applies a filtering preprocessing and then writes the data to the LSL stream as 6 channels (`seq`, `device_clock_us`, `target_raw_count`, `target_current_units`, `target_filtered_units`, `target_status`) at an irregular ~93–100Hz.
  - `HandgripReference`: reads the IPC packages and writes the data to the LSL stream as 4 channels (`seq`, `reference_clock_s`, `reference_force_N`, `reference_status`). The sampling rate of this stream is theoretically set by the acquisition board configured as `Modbus Active-Send` mode at 500Hz. In practice, reaches `498-500Hz`.
  - `HandgripComponentEvents`: Operational JSON marker stream for system metadata.
  
- The `LSL_Viewer` is a Visualization tool that subscribes to `HandgripTarget` and `HandgripReference`. It must perform linear interpolation of the reference stream to match target timestamps for real-time correlation plots (Time-series overlap and Sensor-curve X-Y plot).

- The `Handgrip_Calibration` is the workflow execution module. It manages the full calibration lifecycle:
    1. Preflight and session manifest creation.
    2. Synchronized recording of LSL streams to canonical CSVs (`target.csv`, `reference.csv`).
    3. Execution of the calibration protocols (currently `static_staircase_model_selection_v2`).
    4. Model fitting (Deming regression, hysteresis/drift diagnostics) and generation of `fit_result.json` and Markdown reports.

The purpose of all this components is to provide standardized data streams to the host PC that would allow to calibrate the Handgrip_Firmware based on the reference provided by the acquisition board.

## Measurement setup

For the calibration, a constant force can be applied across the handgrip's sensor and the acquisition board's sensor, both of which are conected in series in order that the force is shared between both sensors, and so the acquisition board measurement can be used as a reference for the Handgrip_Firmware calibration.

# Goal 

Design based on detailed load cell calibration research and industry standards, a set of improved calibration protocols to apply over the measurement setup described above, in order to generate enough data that would enable the handgrip device calibration based on the reference data provided by the acquisition board.

# Task

Based on the current state of the Handgrip_Firmware, LSL_Bridge and the RS485_GUI, and the documentation available in the project files, please design a set of detailed protocols to calibrate the handgrip device based on the reference provided by the acquisition board.

IMPORTANT: For that purpose, review on the web about relevant literature for calibration protocols. 

Base all the protocols on the highest epistemic quality possible, and include at least the following stages:
1. How to setup both devices (is expected that both sensors will be configured in series, and a constant regulable force will be applied across both sensors, so that the force is shared between both sensors). 
2. The force protocols recommended (type: {zero, constant, linear, ladder, ramp, etc}, ranges, speeds, etc), and in which order to apply them.
3. Which data to expect from, and how to analyze it. 
4. Once the calibration is done, how to measure the accuracy of the calibration.
5. How to iterate the calibration process and how to compare it's performance with previous calibrations.
6. Other relevant stages. 
The proposed stages should be reviewed, re-organized (meaning reorder, splitting and merging, refinded and others.) and updated based on the current state of the Handgrip_Firmware, LSL_Bridge and the RS485_GUI, and what's recommended by the relevant recollected information from the web. 

The protocols should be detailed enough to be able to use it as a requirements specification for it's implementation, for the calibration process of the handgrip device.

