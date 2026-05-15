# @package lsl_bridge.io.serial_utils
#  @brief Serial utility helpers for target device connection setup.
##
"""
Serial port utilities for the LSL Bridge.

Provides two small helpers used by the main serial read loop in ``app.py``:

* ``find_port_metadata`` — queries ``serial.tools.list_ports`` for USB
  metadata (VID/PID, serial number, manufacturer) for a named port.
* ``settle_serial_input`` — discards stale UART bytes accumulated during
  device power-on by draining the input buffer for a configured duration.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from serial import Serial
from serial.tools import list_ports

_log = logging.getLogger(__name__)


# @brief Look up USB metadata for a configured serial port.
#  @param port_name Device path such as /dev/ttyUSB0.
#  @return Dictionary with enumerated metadata fields for the target port.
def find_port_metadata(port_name: str) -> dict[str, Any]:
    """
    Return USB metadata for *port_name* from the system port enumeration.

    Args:
        port_name: Device path as a string (e.g. ``"/dev/ttyUSB1"``).

    Returns:
        A dict with keys ``device``, ``description``, ``hwid``, ``vid``,
        ``pid``, ``serial_number``, ``manufacturer``, ``product``.
        If the port is not found in the enumeration, returns
        ``{"device": port_name}`` so callers never receive ``None``.

    """
    for port in list_ports.comports():
        if port.device == port_name:
            return {
                "device": port.device,
                "description": port.description,
                "hwid": port.hwid,
                "vid": port.vid,
                "pid": port.pid,
                "serial_number": getattr(port, "serial_number", None),
                "manufacturer": getattr(port, "manufacturer", None),
                "product": getattr(port, "product", None),
            }
    _log.debug("Port %r not found in comports enumeration; using minimal metadata.", port_name)
    return {"device": port_name}


# @brief Drain serial input bytes during startup settle window.
#  @param ser Open pyserial instance.
#  @param startup_settle_s Settle duration in seconds.
#  @return None.
def settle_serial_input(ser: Serial, startup_settle_s: float) -> None:
    """
    Drain the UART input buffer during the startup settle window.

    Reads and discards lines until *startup_settle_s* seconds have elapsed,
    then performs a final ``reset_input_buffer()`` to flush any partial line.

    Args:
        ser:               Open ``Serial`` instance.
        startup_settle_s:  Duration in seconds.  Values ≤ 0 are treated as
                           no settle (immediate ``reset_input_buffer``).

    """
    ser.reset_input_buffer()
    deadline = time.monotonic() + max(0.0, startup_settle_s)
    while time.monotonic() < deadline:
        ser.readline()
    ser.reset_input_buffer()
    _log.debug("Serial input buffer settled (%.2fs).", startup_settle_s)
