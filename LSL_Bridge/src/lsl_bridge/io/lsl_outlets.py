# @package lsl_bridge.io.lsl_outlets
#  @brief StreamInfo and StreamOutlet builders for target/reference streams.
##
"""
LSL StreamOutlet construction for the LSL Bridge.

Builds the two data outlets (HandgripTarget, HandgripReference) and provides
helper utilities for populating LSL stream descriptors.

Channel counts are derived dynamically from ``len(cfg.streams.*.channels)``
so that adding or removing channels in config automatically propagates to the
outlet without any source-code change.

Schema version strings and outlet chunk sizes are driven by config to avoid
magic literals in code.
"""

from __future__ import annotations

import logging
from typing import Any

from omegaconf import DictConfig
from pylsl import IRREGULAR_RATE, StreamInfo, StreamOutlet, cf_double64

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Low-level descriptor helpers
# ---------------------------------------------------------------------------


def _append_channel(channels: Any, label: str, channel_type: str, unit: str) -> None:
    """Append a single &lt;channel&gt; element to a LSL descriptor node."""
    ch = channels.append_child("channel")
    ch.append_child_value("label", str(label))
    ch.append_child_value("type", str(channel_type))
    ch.append_child_value("unit", str(unit))


def _append_metadata(desc: Any, metadata: dict[str, Any]) -> None:
    """Append key/value pairs to a LSL descriptor node; skips ``None`` values."""
    for key, value in metadata.items():
        if value is not None:
            desc.append_child_value(str(key), str(value))


# ---------------------------------------------------------------------------
# Source-ID resolution
# ---------------------------------------------------------------------------


# @brief Resolve source_id for the target outlet.
#  @param cfg Full Hydra configuration.
#  @param port_meta Enumerated target serial metadata.
#  @return Stable source identifier string for the target stream.
def build_target_source_id(cfg: DictConfig, port_meta: dict[str, Any]) -> str:
    """
    Resolve the LSL source_id for the target stream.

    Prefers the explicit ``streams.target.source_id`` from config; falls back
    to the USB serial number, then a sanitised device path.

    Args:
        cfg:       Full Hydra ``DictConfig``.
        port_meta: Metadata dict from ``find_port_metadata()``.

    Returns:
        A stable, unique-ish LSL source_id string.

    """
    explicit = cfg.streams.target.get("source_id")
    if explicit:
        return str(explicit)
    serial_number = port_meta.get("serial_number")
    if serial_number:
        return f"arduino-handgrip-{serial_number}"
    device = str(port_meta.get("device", "unknown")).replace("/", "_")
    return f"arduino-handgrip-{device}"


# ---------------------------------------------------------------------------
# Outlet factories
# ---------------------------------------------------------------------------


# @brief Build the HandgripTarget LSL outlet.
#  @param cfg Full Hydra configuration.
#  @param source_id Source identifier string for StreamInfo.
#  @return Configured StreamOutlet for target samples.
def build_target_outlet(cfg: DictConfig, source_id: str) -> StreamOutlet:
    """
    Construct the HandgripTarget LSL outlet.

    Channel count is derived from ``cfg.streams.target.channels`` so it
    stays in sync with the config without hard-coding.

    Args:
        cfg:       Full Hydra ``DictConfig``.
        source_id: Resolved source_id string (from ``build_target_source_id``).

    Returns:
        A ready ``StreamOutlet`` instance.

    """
    stream_cfg = cfg.streams.target
    n_channels = len(stream_cfg.channels)
    info = StreamInfo(
        str(stream_cfg.name),
        str(stream_cfg.type),
        n_channels,
        IRREGULAR_RATE,
        cf_double64,
        source_id,
    )
    desc = info.desc()
    _append_metadata(
        desc,
        {
            "schema": str(stream_cfg.schema),
            "session_id": cfg.session.get("session_id"),
            "manufacturer": stream_cfg.manufacturer,
            "device_name": stream_cfg.device_name,
            "payload_schema": stream_cfg.payload_schema,
            "sampling_model": "target_native_irregular",
            "timestamp_policy": cfg.target_timestamping.policy,
            "clock_semantics": ("LSL timestamp is synchronization authority; device_clock_us is diagnostic"),
            "fit_signal": "target_raw_count",
        },
    )
    channels = desc.append_child("channels")
    for channel_key in stream_cfg.channels:
        c = stream_cfg.channels[channel_key]
        _append_channel(channels, c.label, c.type, c.unit)

    outlet = StreamOutlet(info, chunk_size=int(stream_cfg.chunk_size))
    _log.info(
        "Target LSL outlet created: name=%s source_id=%s channels=%d",
        stream_cfg.name,
        source_id,
        n_channels,
    )
    return outlet


# @brief Build the HandgripReference LSL outlet.
#  @param cfg Full Hydra configuration.
#  @return Configured StreamOutlet for reference samples.
def build_reference_outlet(cfg: DictConfig) -> StreamOutlet:
    """
    Construct the HandgripReference LSL outlet.

    Args:
        cfg: Full Hydra ``DictConfig``.

    Returns:
        A ready ``StreamOutlet`` instance.

    """
    stream_cfg = cfg.streams.reference
    source_id = (
        "rs485-reference"
        if stream_cfg.source_id is None
        else str(stream_cfg.source_id)
    )
    n_channels = len(stream_cfg.channels)
    info = StreamInfo(
        str(stream_cfg.name),
        str(stream_cfg.type),
        n_channels,
        float(stream_cfg.nominal_srate),
        cf_double64,
        source_id,
    )
    desc = info.desc()
    _append_metadata(
        desc,
        {
            "schema": str(stream_cfg.schema),
            "session_id": cfg.session.get("session_id"),
            "manufacturer": stream_cfg.manufacturer,
            "device_name": stream_cfg.device_name,
            "sampling_model": "reference_native_regular",
            "nominal_srate_hz": stream_cfg.nominal_srate,
            "rs485_ipc_endpoint": cfg.rs485_ipc.connect,
            "clock_semantics": (
                "LSL timestamp is synchronization authority; "
                "reference_clock_s is diagnostic"
            ),
            "fit_signal": "reference_force_N",
        },
    )
    channels = desc.append_child("channels")
    for channel_key in stream_cfg.channels:
        c = stream_cfg.channels[channel_key]
        _append_channel(channels, c.label, c.type, c.unit)

    outlet = StreamOutlet(info, chunk_size=int(stream_cfg.chunk_size))
    _log.info(
        "Reference LSL outlet created: name=%s source_id=%s channels=%d srate=%.1f",
        stream_cfg.name,
        source_id,
        n_channels,
        float(stream_cfg.nominal_srate),
    )
    return outlet
