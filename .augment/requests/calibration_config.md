
# Context 

## Devices Description 

### Acquisition Board - Calibration Reference
I have a device (an acquisition board for a load cell rated up to 100Kg), 
This acquisition board: 
  - can be configured to one of the following sampling rates  {10hz, 40hz, 640hz, 1280hz}
  - is connected to my host PC (linux) via RS485 to USB. 
    - This RS485 communication:  
      - support up to 600000 baud (can be set to {2400, 4800, 9600, 19200, 22800, 38400, 57600, 115200, 128000, 230400, 256000, 460800, 500000, 512000, 600000,} 
      - Uses Modbus protocol for it's communication. 
        - This Modbus protocol supports: 
          - Modbus RTU mode  
          - Modbus Active mode
            - This Modbus Active mode supports up to 1000Hz (can be set to {1, 2, 5, 10 , 20, 25, 50, 100, 500, 1000} )
Other characteristics of the aquisition board are attached on the file `high_speed_acquisition_instrument_reorganized_manual.md`



### Sensor Device - Calibration Target
At the other hand, I have another target device: 
  - based on an HX711 that receives two load cells in parallel (rated up to 5 or 10 Kg each (not known which, but known that the device was designed to measure hand grip force).  
  - Has an average sampling rate of ~93Hz +- 15ms (not fully consistent) 
  - Also communicates to the same PC via UART serial communication 
    - This UART is configured to 115200U baud in an  Arduino Nano (Atmel MEGA328PB) that has app 3~4 años unused. 
    - Also the device reports with the following format: `/* Format for LSL Bridge: D,<seq>,<timestamp_us>,<value>\n */` and the LSL bridge also has it's own master timestamp.

Both devices have the optional possibility of connecting to a Lab Streaming Layer. 

# Goal 
The goal of the task is to optimize the configuration of the reference and target devices, and the configuration of the communication protocol  in order to enable the best possible calibration of the target device. 

# Task
1. Integrate all the info provided, 
2. Review the documentation to understand ALL the available configuration parameters
3. Review the web for complementary information, in regard to both the hardware and the engineering domain of the task (Digital Siganl Processing) 
4. Provide with the best configuration for all the parameters specified (except the ~93Hz average sampling rate which the max sampling rate empirically achieved) 

## Deliverable requirements: 
- Report a markdown file 
- Start with an overview
- Next continue with a Summary in a table the recommended configuration values => be detailed and optimize the understanding of the reason to choose that value. 
- Finally a detailed break down of the recommended value for each configuration specifiying: 
  - Overall reason for the selected value 
  - How impacts (or not) into improve the calibration 
  - 2-3 suitable alternatives and why they were rejected in favor of the recommended value. 


