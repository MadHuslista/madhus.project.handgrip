Please apply the following UI changes: 

# Related to the plot
1. Add a button that clean the signal trace from the plot whenever is pressed.
2. Add a toggle to the plot (activated by default) that cleans the signal trace (as in 1) at the beginning of each new connection with the target.
   1. If disabled, the plot should behave as it the plot was before the toggle was added.
3. Add a dropdown to the plot that allows to select the plotted signal (internal_code_raw_value, raw_value, peak_value, net_value, gross_raw, net_raw, etc); all of them should be available, but only one can be plotted at a time. 
   1. The change of the plotted signal should be reflected as a hot-reload of the page: the plot should be updated with the new signal, and the legends and axis legends should be updated accordingly, but keeping the same section of the plot visible.
   2. The change of the plotted signal should be reflected also in the label and ranges of the plotted signal.
   3. For each signal it should be added -as a legend- the values used to calculate the plotted signal: decimal_code, unit_code, status_word, parsed_from, timestamp_source, etc; along a mini description of the value (e.g. the unit of the signal, the interpretation of the status word, etc). that appears only if hovering the mouse over the legend or clicking on it (whichever is easier to implement).
   4. The default signal to should be configurable and should be the interpreted signal.
4. Add a card to the plot that shows the -measured- average sampling rate of the signal received from the target.
   1. This means that the average sampling rate of the signal received from the target, after processing it's timestamp for each sample -as currently- it should be displayed in the plot as a running average of a sliding window of the last <configurable> samples. 
   2. The card should show the target sampling rate, the average sampling rate in Hz measured from the assigned timestamps of the processed signal, along with the standard deviation of the sampling rate. Also, the card should show the number of samples that were received from the target, and the number of samples that were dropped because of the configured maximum sampling rate.

# Layout
4. Put the "Current effective board-side communication settings you should mirror on the instrument" under the "Connection" config section
5. Move the "Modbus actions / commands" section to the bottom of the page; and hide them under a dropdown called "Advanced Actions".
   1. If the mode is "active_send", the dropdown should be disabled.
   2. The modbus actions section should be disabled by default and only be enabled when the mode is "modbus_rtu".
   3. The layout of the commands should be vertical, instead of horizontal.
      1. For each command, it should have a short description of what it does to the right of the command button, along whith the equivalent of the command in the device manual, as it were applied manually.
      2. The commands should be listed in the same order as they appear in the device manual.
   4. Each of the advanced actioins should have a description of what it does, and which would be the equivalent of the command in the device manual.

# Misc
1. For the loggers, please add a message with the current absolute path of the corresponding log file


Return as deliverable the updated python script and configuration file.