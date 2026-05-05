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

Extend the current any (or all, or none) of the firmware and applications, in order to provide the required features to properly record the data needed for the calibration, during the execution of the calibration workflows.

# Task

1. Independently of the current software & firmware, identify which would be the ideal set of features needed to capture the data provided by the acquisition board and the handgrip device in order to perform the calibration.
2. Compare the current firmware and software with the ideal set of features, and identify the missing features.
3. Identify if the missing features are better to be implemented as a new python module, or as an extension to the current firmware and software.
4. If the missing features are better to be implemented as a new python module, then design the new module and provide a detailed plan for its implementation.
5. If the missing features are better to be implemented as an extension to the current firmware and software, then design the new extension and provide a detailed plan for its implementation.

IMPORTANT: For that purpose, review on the web about relevant literature for calibration workflows. 

# Deliverable: 
1. A detailed plan for the implementation of the missing features, either as a new python module or as an extension to the current firmware and software.
