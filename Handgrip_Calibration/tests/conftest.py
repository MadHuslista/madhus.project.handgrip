"""Pytest configuration and shared fixtures for handgrip_calibration tests.

Ensures Hydra's GlobalHydra singleton is cleared between test runs so that
multiple calls to ``load_config()`` in the same session do not collide.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def clear_hydra_state() -> None:
    """Clear Hydra's global state before every test.

    ``load_config()`` calls ``initialize_config_dir()`` which registers state
    in Hydra's singleton.  Without clearing, subsequent calls within the same
    pytest session raise ``GlobalHydraInitializationException``.
    """
    try:
        from hydra.core.global_hydra import GlobalHydra

        GlobalHydra.instance().clear()
    except ImportError:
        pass  # hydra-core not installed — plain yaml fallback is used
