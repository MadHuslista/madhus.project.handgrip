
# Context

Please review the LSL_Bridge
- Currently the LSL_Bridge reads the data from the serial port, applies a filtering preprocessing and then writes the data to the LSL stream as three channels: raw, filtered and clock.
- The LSL_Viewer reads the data from the LSL stream and displays it in a live plot.

In parallel review the RS485_GUI code
- Currently the RS485_GUI reads the data from the RS485 port in Modbus Active-Send mode at 500Hz. 

# Goal 

Include the RS485 - Modbus RTU and RS485 - Modbus Active-Send modes from the RS458_GUI as new channels into the an extended version of the LSL_Bridge.

# Task

Plan how to extend the RS485_GUI to emit the data in Modbus RTU mode (depending on configuration) and Modbus Active-Send mode (depending on configuration), so that the LSL_Bridge can read it and write it to the LSL stream as two new channels: raw and clock (on RTU mode, the clock is the host clock, on Active-Send mode, it is the device clock to the frequency code specified in the configuration; following the same logic as the RS485_GUI).

Plan how to extend the LSL_Bridge to read emitted from the RS485_GUI in Modbus RTU mode and Modbus Active-Send mode, and write it to the LSL stream as two new channels: raw and clock (on RTU mode, the clock is the host clock, on Active-Send mode, it is the device clock to the frequency code specified in the configuration; following the same logic as the RS485_GUI).

## Requirements
- All the signal should be synchronized with the host clock
- The LSL stream should emit 5 channels: 3 for the target device (currently implemented as raw, filtered and clock), and 2 for the acquisition board readings via the RS485_GUI. 



---------------------------

# Context
Review the current implementation of `LSL_Bridge/handgrip_lsl_bridge.py` and `RS485_GUI/acquisition_board_gui.py`. 
- The `LSL_Bridge` currently manages a single serial connection to an Arduino, publishing a 3-channel LSL stream: `device_clock_us`, `grip_force_raw`, and `grip_force_filtered`.
- The `RS485_GUI` uses a `BoardTransport` abstraction to read from a high-speed acquisition board via RS485 in either **Modbus RTU** (polling) or **Active-Send** (push) modes, typically at 500Hz.

# Goal
Extend the system so that the `LSL_Bridge` outputs a unified 5-channel LSL stream that includes both the existing handgrip data and the RS485 acquisition board data.

# Task
Provide a technical plan to implement the following:

1.  **RS485_GUI Data Emission**: Plan an Inter-Process Communication (IPC) mechanism (e.g., ZMQ, local UDP socket, or shared queue) within `RS485_GUI/acquisition_board_gui.py` to emit `MeasurementFrame` data. This should be toggleable via configuration so the GUI can act as a data provider for the bridge.
2.  **LSL_Bridge Extension**: 
    - Modify `handgrip_lsl_bridge.py` to ingest the data emitted by the `RS485_GUI`.
    - Update the `StreamInfo` and `StreamOutlet` to support 5 channels:
        - Ch 0: `device_clock_us` (Arduino)
        - Ch 1: `grip_force_raw` (Arduino)
        - Ch 2: `grip_force_filtered` (Arduino)
        - Ch 3: `rs485_raw` (Acquisition Board)
        - Ch 4: `rs485_clock` (Acquisition Board)
3.  **Clock Logic**:
    - In **Modbus RTU mode**, `rs485_clock` must use the host clock (`pylsl.local_clock()`).
    - In **Active-Send mode**, `rs485_clock` must use the reconstructed device clock based on the frequency code (e.g., 500Hz), following the logic in `RS485_GUI/acquisition_board_gui.py`.
4.  **Configuration**: Define the necessary additions to `LSL_Bridge/conf/config.yaml` and `RS485_GUI/config.yaml` to manage this connection (e.g., IPC ports, enabling/disabling the extended channels).

# Requirements
- **Synchronization**: All 5 channels must be pushed in a single `outlet.push_sample()` call or correctly time-aligned using a shared host-side LSL timestamp to ensure synchronization.
- **Robustness**: The bridge should handle cases where the `RS485_GUI` is not running or the RS485 stream is interrupted without crashing the primary handgrip acquisition.