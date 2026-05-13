"""Allow ``python -m handgrip_calibration`` as an entry point."""

from __future__ import annotations

from .cli import main

raise SystemExit(main())
