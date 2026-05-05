# Context

Please review the current state of the Handgrip_Firmware, LSL_Bridge, LSL_Viewer and the RS485_GUI. All 4 components works together to reads and provides a data streams to the host PC.
- The `Handgrip_Firmware` is the main firmware that runs on the Arduino Nano. It reads the load cell sensor data on the Arduino via the HX711, packs it into a unified format including data and internal timestamp, and sends it to the serial port using UART.
- The `RS485_GUI` is the Python application that reads the data from Acquisition Board via RS485 in either **Modbus RTU** (polling) or **Active-Send** (push) modes, typically at 500Hz, and shows it in a live plot, and also sends it via IPC to the `LSL_Bridge` 
- The `LSL_Bridge` is the Python application in charge to standardize the data streams into two LSL streams: one for the Handgrip_Firmware and one for the RS485_GUI. 
  - For the The Handgrip_Firmware stream, it applies a filtering preprocessing and then writes the data to the LSL stream as three channels: raw, filtered and clock. The sampling rate of this stream is unconsistent but averages to 93~100Hz.  
  - For the RS485_GUI stream it reads the IPC packages and writes the data to the LSL stream as two channels: raw and clock. The sampling rate of this stream is theoretically set by the acquisition board configured as `Modbus Active-Send` mode at 500Hz. In practice, reaches `498-500Hz`.

- The `LSL_Viewer` is a Python application that reads the 2 LSL streams and displays them in live time-series plots for each independent stream and two correlation plots that sync both signals and show it's correlation as an overlaped time-series plot and as a sensor-curve plot where the acquisition board is set as the reference on the x-axis and the Handgrip_Firmware is set as the target on the y-axis.

The purpose of all this components is to provide standardized data streams to the host PC that would allow to calibrate the Handgrip_Firmware based on the reference provided by the acquisition board.

## Measurement setup

For the calibration, a constant force is applied across the handgrip's sensor and the acquisition board's sensor, both of which are conected in series in order that the force is shared between both sensors, and so the acquisition board measurement can be used as a reference for the Handgrip_Firmware calibration.


# Goal 

Design a calibration set of workflows to apply over the measurement setup described above, in order to generate enough data that would enable the handgrip device calibration based on the reference data provided by the acquisition board.

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


