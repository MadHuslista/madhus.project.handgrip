"""Abstract base class for RS485 board transports.

Both ``ModbusBoardTransport`` and ``ActiveSendBoardTransport`` must implement
all abstract methods.  Calling code uses only this interface.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from rs485_gui.models import MeasurementFrame


class BoardTransport(ABC):
    """Abstract interface for communicating with the acquisition board."""

    @abstractmethod
    def connect(self) -> None:
        """Open the serial port and initialise the transport state."""

    @abstractmethod
    def disconnect(self) -> None:
        """Close the serial port and release all resources."""

    @abstractmethod
    def read_frames(self) -> list[MeasurementFrame]:
        """Read one or more frames from the board.

        Returns a list of decoded :class:`~rs485_gui.models.MeasurementFrame`
        objects.  Must block until at least one frame is available or raise
        :class:`TimeoutError` if the read deadline expires.
        """

    @abstractmethod
    def send_command(self, command_name: str) -> None:
        """Write a named command to the board.

        Raises :class:`RuntimeError` if not supported in the current mode.
        """
