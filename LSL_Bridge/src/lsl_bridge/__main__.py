# @package lsl_bridge.__main__
#  @brief Module entry point for running the bridge via python -m.
##
"""
Enable ``python -m lsl_bridge`` as an entry point.

Equivalent to running the ``lsl-bridge`` console script defined in
``pyproject.toml``.  Hydra handles argument parsing and config composition.

Usage::

    python -m lsl_bridge
    python -m lsl_bridge serial.port=/dev/ttyUSB0
    python -m lsl_bridge logging=debug
"""

import sys

from lsl_bridge.app import main

sys.exit(main())
