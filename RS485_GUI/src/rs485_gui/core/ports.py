"""Serial port discovery and exclusion filtering.

Dependency chain: models, constants  (no I/O beyond pyserial list_ports)
"""
from __future__ import annotations

import logging

from omegaconf import DictConfig
from serial.tools import list_ports

from rs485_gui.models import PortInfo

LOGGER = logging.getLogger(__name__)


def enumerate_ports(port_hints: list[str]) -> list[PortInfo]:
    """Return all available COM/tty ports, scored by *port_hints* substring matches.

    Ports with more hint matches rank higher.  Ties are broken by device name.
    """
    ports: list[PortInfo] = []
    for p in list_ports.comports():
        haystack = ' '.join(filter(None, [p.device, p.description, p.hwid])).upper()
        score = sum(1 for hint in port_hints if hint.upper() in haystack)
        ports.append(
            PortInfo(
                device=p.device,
                description=p.description or '',
                hwid=p.hwid or '',
                vid=p.vid,
                pid=p.pid,
                score=score,
            )
        )
    ports.sort(key=lambda item: (-item.score, item.device))
    return ports


def get_excluded_serial_ports(cfg: DictConfig) -> list[str]:
    """Return the list of serial ports that this GUI must not open.

    Prevents accidental contention with the Arduino/LSL bridge port.
    """
    raw = cfg.serial.excluded_ports
    if raw is None:
        return []
    try:
        return [str(item) for item in list(raw) if str(item).strip()]
    except TypeError:
        return [str(raw)] if str(raw).strip() else []


def is_serial_port_excluded(cfg: DictConfig, port: str) -> bool:
    """Return ``True`` if *port* is on the excluded list."""
    port_str = str(port or '')
    if not port_str:
        return False
    return port_str in set(get_excluded_serial_ports(cfg))


def filter_excluded_ports(cfg: DictConfig, ports: list[PortInfo]) -> list[PortInfo]:
    """Remove any excluded ports from *ports* and return the filtered list."""
    excluded = set(get_excluded_serial_ports(cfg))
    if not excluded:
        return ports
    return [p for p in ports if p.device not in excluded]
