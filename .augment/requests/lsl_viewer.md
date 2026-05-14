
Based on the current state of the LSL_Bridge, RS485_GUI and the RS485_GUI, and the attached documentation as a markdown file, please extend the LSL_Viewer to show the new two channels coming from the RS485_GUI (only if they are present, if not then the viewer should behave as it does now).

If the channels from the RS485_GUI are present, then the viewer should show them in the same way as it currently shows the raw and clock channels from the target device, but now from the RS485_GUI.

Each channel should be labeled with the name of the signal it represents, run in it's own subplot, and the channel should be colored according to the signal type (raw, filtered, clock).

Also if the channels from the RS485_GUI are present, then the viewer should show add 2 new subplot plotting the raw signal from the target device vs the raw signal from the RS485_GUI, both signals being synced to the same time, based on their respective clocks.
- The first subplot should have on the X-axis the time in milliseconds, and on the Y-axis the raw signal from the target device normalized to N, and the raw signal from the RS485_GUI normalized to N. 
- The second subplot should have on the X-axis the raw signal from the target device normalized to N, and on the Y-axis the raw signal from the RS485_GUI normalized to N.



----------------------

Extend `LSL_Viewer/handgrip_realtime_viewer.py` to support the updated 5-channel LSL stream produced by the `LSL_Bridge`. The viewer must dynamically adapt its layout based on whether the extra RS485 channels are present in the incoming LSL stream metadata.

### 1. Channel Detection and Backward Compatibility
- Inspect the LSL `StreamInfo` upon connection. 
- If the stream contains 5 channels (matching the `UnifiedHandgripRS485` schema), enable the extended visualization.
- If the stream contains only the original 3 channels (`device_clock_us`, `grip_force_raw`, `grip_force_filtered`), the viewer must maintain its current 3-panel layout without errors.

### 2. UI Layout Extensions (for 5-channel mode)
When the RS485 channels are detected, add the following subplots to the Matplotlib figure:
- **RS485 Raw Signal**: Plot the `rs485_raw` channel (Channel 3).
- **RS485 Sample Interval**: Calculate the delta between consecutive `rs485_clock` (Channel 4) values and plot the interval in milliseconds, similar to the existing "device sample interval" panel.
- **Synchronization Comparison**: Add a dedicated subplot that overlays `grip_force_raw` (Channel 1) and `rs485_raw` (Channel 3) on the same X-axis. 
    - **Time Alignment**: Since `device_clock_us` is in microseconds and `rs485_clock` is in seconds (as per `LSL_Bridge/conf/config.yaml`), normalize both to a shared host-relative or zero-indexed timebase for this plot.
    - **Scaling**: Note that units differ (`g` for handgrip vs `N` for RS485); consider using twin Y-axes or normalized scaling for visual alignment.

### 3. Visual Styling and Labeling
- **Labeling**: Use the semantic labels defined in `LSL_Bridge/conf/config.yaml` (`rs485_raw`, `rs485_clock`) for subplot titles and legends.
- **Color Coding**: Maintain a consistent color scheme across all panels:
    - **Raw signals**: Use the same color for `grip_force_raw` and `rs485_raw` (e.g., Blue).
    - **Filtered signals**: Use a distinct color (e.g., Green).
    - **Clock/Interval metrics**: Use a distinct color for timing jitter panels (e.g., Red or Orange).
- **Replay Support**: Ensure these new subplots are also populated when running in `csv_replay` or `xdf_replay` modes, provided the source files contain the 5-channel data.

### 4. Configuration
Update `LSL_Viewer/conf/config.yaml` to include optional keys for the new channels (e.g., `rs485_raw_label`, `rs485_clock_label`) to ensure the viewer remains synchronized with the bridge's output schema.


--------------------------------------

# Context
Please review the current state of the LSL_Bridge
    - Currently the LSL_Bridge reads the data from the serial port, applies a filtering preprocessing and then writes the data to the LSL stream as three channels: raw, filtered and clock.
    - Also the LSL_Bridge reads the data from the RS485 IPC and writes the data to the LSL stream as two channels: raw and clock.

In parallel the LSL_Viewer reads the data from the LSL stream and displays it in a live plot, although the plot is currently configured to display only the original 3 channels (raw, filtered, clock).

# Goal
Extend `LSL_Viewer/handgrip_realtime_viewer.py` to support the unified 5-channel LSL stream produced by the updated `LSL_Bridge`. The viewer must dynamically adapt its layout based on whether the extra RS485 channels are detected in the stream metadata or replay files.

# Task
Provide a technical plan to implement the following features:

### 1. Dynamic Channel Detection & Backward Compatibility
- Modify `validate_live_stream`, `load_csv_replay`, and `load_xdf_replay` to check for the presence of RS485 channels using labels from `LSL_Bridge/conf/config.yaml` (`rs485_raw`, `rs485_clock`).
- If only the original 3 channels (`device_clock_us`, `grip_force_raw`, `grip_force_filtered`) are present, maintain the current 4-panel layout (Info, Raw, Filtered, Interval).
- Make sure that the interpretation of the meaurement unit for the `grip_force_raw` and `grip_force_filtered` channels to be `N` instead of `g`.
- If all 5 channels are present, enable the extended visualization mode.

### 2. UI Layout Extensions (5-Channel Mode)
Update `init_figure` and the render loops (`run_live_mode`, `run_replay_mode`) to include the following additional subplots:
- **RS485 Raw Signal**: A rolling plot of the `rs485_raw` channel.
- **RS485 Sample Interval**: A plot of the delta between consecutive `rs485_clock` values, converted to milliseconds (ms).
- **Time-Synchronized Comparison**: A subplot overlaying the target device raw signal and the RS485 raw signal.
    - **X-axis**: Relative time in milliseconds (ms).
    - **Y-axis**: Both signals normalized to Newtons (N).
    - **Alignment**: Synchronize `device_clock_us` (microseconds) and `rs485_clock` (seconds) to a shared relative timebase.
- **XY Correlation Plot**: A line plot comparing the two raw signals.
    - **X-axis**: Target device raw signal (normalized to N).
    - **Y-axis**: RS485 raw signal (normalized to N).
    - **Aligment**: Since both signals have different sampling rates, make sure both axes are synchronized to the same timebase.
    - **Rendering Update**: Similar to the other time-series plots, this plot should render continuously as new data arrives, with a configurable amount of last-seen data to display (e.g. last 10 seconds). 
      - Ideally, the signal should fade out as it moves out of the visible time-window, avoiding the clutter of old data.

### 3. Visual Styling & Configuration
- **Color Coding**: 
    - Use consistent colors for "Raw" types (e.g., Red for both handgrip and RS485 raw).
    - Use a distinct color for "Filtered" (e.g., Green).
    - Use a distinct color for "Clock/Interval" metrics (e.g., Blue).
- **Labeling**: Use semantic labels from the config for all titles and legends.
- **Configuration**: Update `LSL_Viewer/conf/config.yaml` to include keys for `rs485_raw_label` and `rs485_clock_label` under the `channels` section to match the bridge schema.

### 4. Replay Support
Ensure `_window_from_replay` and the replay logic correctly slice and process all 5 channels for the new subplots when using `csv_replay` or `xdf_replay` modes.


-----------------------------------


### Context
The `LSL_Bridge` has been updated to produce a unified 5-channel LSL stream. In addition to the original 3 channels from the Arduino handgrip (`device_clock_us`, `grip_force_raw`, `grip_force_filtered`), it now includes 2 channels from an RS485 acquisition board (`rs485_raw`, `rs485_clock`). 

The `LSL_Viewer` currently only supports the 3-channel layout. We need to extend `LSL_Viewer/handgrip_realtime_viewer.py` to dynamically detect and visualize all 5 channels while maintaining backward compatibility for legacy 3-channel streams and replay files.

### Goal
Update the `LSL_Viewer` to support the 5-channel "Unified" stream. The UI must adapt its layout based on the detected channel count in live, CSV, and XDF modes.

### Task: Technical Implementation Plan

Provide a technical plan to implement the following:

#### 1. Configuration & Metadata Update
- **Update `LSL_Viewer/conf/config.yaml`**: Add `rs485_raw_label: rs485_raw` and `rs485_clock_label: rs485_clock` under the `channels` section to match the `LSL_Bridge` schema.
- **Unit Correction**: Ensure all force-related labels and axes use `N` (Newtons) as the unit. Verify that no legacy `g` (grams) references remain in the display logic.

#### 2. Dynamic Channel Detection & Data Structures
- **Dataclass Updates**: Extend `LiveWindow` and `ReplayData` to include optional fields for `rs485_raw` and `rs485_clock`.
- **Detection Logic**: 
    - Modify `validate_live_stream` to check for the presence of the new RS485 labels in `stream.ch_names`.
    - Update `load_csv_replay` and `load_xdf_replay` to attempt to resolve these 5 channels, falling back gracefully to 3-channel mode if the RS485 labels are missing.
- **Data Fetching**: Update `fetch_live_window` to pick all 5 channels if available.

#### 3. UI Layout & Visualization (5-Channel Mode)
Modify `init_figure` to support a dynamic grid (e.g., using `matplotlib.gridspec`). If 5 channels are detected, expand the layout to include:
- **RS485 Raw Signal**: A rolling time-series plot of `rs485_raw`.
- **RS485 Sample Interval**: A plot showing the delta (in ms) between consecutive `rs485_clock` samples. Note: `rs485_clock` is in seconds, so calculate `diff * 1000`.
- **Time-Synchronized Overlay**: A subplot overlaying `grip_force_raw` and `rs485_raw`.
    - **Alignment**: Normalize `device_clock_us` (convert from $\mu s$ to $s$) and `rs485_clock` ($s$) to a shared relative timebase ($t=0$ at the end of the window).
- **XY Correlation Plot**: A plot with `grip_force_raw` on the X-axis and `rs485_raw` on the Y-axis.
    - **Resampling**: Since the Arduino (~100Hz) and RS485 (~500Hz) have different rates, use linear interpolation to align the signals for the XY plot.
    - **Visual Fade**: Implement a "trailing" effect where older points in the current window have lower alpha/opacity to reduce clutter.

#### 4. Visual Styling
- **Consistent Coloring**:
    - **Raw Signals**: Red (both Handgrip and RS485).
    - **Filtered Signals**: Green.
    - **Timing/Intervals**: Blue.
- **Info Panel**: Update `_zip_columns` or the text rendering in `run_live_mode`/`run_replay_mode` to display metrics for both sources (e.g., separate rates and latest values for Handgrip vs. RS485).

#### 5. Replay & Logic Consistency
- Ensure `_window_from_replay` correctly slices the additional channels.
- Update the render loops in `run_live_mode` and `run_replay_mode` to handle the conditional plotting of the extra 4 subplots only when the RS485 data is present.




==============================



Based on the "Tool Design Guides" and modern Python packaging standards, perform a comprehensive technical audit and create a GUI porting plan for the attached .zip file from current Matplotlib GUI to NiceGUI, or refactoring Matplotlib

# Pain Point to Overcome
The current Matplotlib GUI capture the focus on every frame, so it became imposible to execute any other task on the host PC while executing the viewer. 
The only alternative is to close the viewer while needing to execute other tasks, for example, the calibration CLI workflow. 

# Goal
Refactor the viewer GUI to be able to showcase and display the full set of features currently implemented, without hoarding the focus on every frame, thus allowing to interact in parallel with the other GUIs and elements of the system. 
Standardize the refactored library architecture to keep maintainability, configuration management, and observability using Python best practices.

# Plausible Alternatives
- Port the App to the NiceGUI framework: Known framework already successfully working with single plot display. 
- Refactor the MatplotLib GUI: Possible easier? 

# Tasks
1. **Pain Point Diagnostic**
   - Based on the symptom description, review the code and identify a set of plausible causes. 
   - Identify the root cause (or causes) that provoque the pain point (even if it's not a 'bug'). All causes needs to be justified by code. 
   - Design a set of plausible "ideal" fixes for the root cause(s), that would solve the paint point in the best way possible. 
   - Compare the advantages or disadvantages of fixing the Matplotlib GUI or poriting the library to NiceGUI, considering the root cause(s) and plausible 'ideal' fixes. 

2. **System Inventory & Evaluation**:
    - Identify and document all existing features.
    - Design an "ideal" architecture for the application, that would solve the pain point, the root cause, and apply the best set of fixes, while also optimizing for maintainability, configuration management, and observability.
    - Map the current architecture and contrast it with the ideal architecture, and evaluate its gap, specifically focusing on how to achieve full feature parity wiht the original while fixing the pain point.


3. **Refactoring Strategy**:
    Plan the transition to a modern stack with the following requirements:
    - **Structural Layout**: Keep the `src-layout` (e.g., `LSL_Bridge/src/lsl_bridge/`) to ensure proper package isolation and testing.
    - **Dependency Management**: Update the standard `pyproject.toml` for the sub-module using PEP 621 metadata, using `uv` as the python package manager and  `hatchling` as the build system. 
    - **Configuration**: Standardize on `Hydra` for configuration management. Ensure to not generate conflicts with the usage of other libraries. Avoid hard-coded 'magic' values, and instead define them as constants in the configuration schema.
    - **Observability**: Implement a hierarchical logging system using the standard `logging` library. Replace ad-hoc logging with loggers scoped to modules (e.g., `logging.getLogger(__name__)`) and configurable levels (DEBUG to CRITICAL) via Hydra. Ensure that any logging that goes to the console is also captured in a .log file.
    - **Feature Completeness**: Ensure that ALL the original features that were touched by the refactor, are still present and working as originally intended (unless purposefully removed - se below). Keep full compatibility with the existing CLI and API; and ensure that the application is still functional and compatible with it's original endpoints.

4. **Code Pruning & Debt Identification**:
    Identify and mark for removal:
    - **Legacy Compatibility**: Unused parsers or protocol handlers (e.g., `legacy_pair_lines` mentioned in documentation but potentially obsolete).
    - **Dead Code**: Features or helper functions left over from the initial development of the HX711 or RS485 integration that are no longer referenced.
    - **Bloated Defensive Programming**: Evaluate and simplify "over-defensive" error handling that overlaps with the underlying `pyserial` or `pylsl` robust error management.

# Deliverable
4. Provide the complete refactor plan in a structured Markdown format (`<module_name>_refactor_plan.md`). This document should include the proposed file tree, a mapping of configuration migrations, and a checklist of code sections to be deprecated.
