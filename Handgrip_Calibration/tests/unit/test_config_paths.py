from __future__ import annotations

from pathlib import Path

import pytest

from handgrip_calibration.config_schema import (
    PACKAGE_ROOT,
    SessionConfig,
    load_config,
    resolve_session_dir,
)


def test_session_config_root_dir_anchored_to_package_root() -> None:
    cfg = SessionConfig.from_mapping({})
    assert cfg.root_dir == PACKAGE_ROOT / "data" / "calibration"
    assert cfg.root_dir.is_absolute()


def test_session_config_copy_component_configs_anchored_to_package_root() -> None:
    cfg = SessionConfig.from_mapping(
        {"copy_component_configs": ["../LSL_Bridge/conf/config.yaml"]}
    )
    assert cfg.copy_component_configs == [PACKAGE_ROOT / "../LSL_Bridge/conf/config.yaml"]
    assert cfg.copy_component_configs[0].is_absolute()


@pytest.mark.parametrize("cwd", [PACKAGE_ROOT, PACKAGE_ROOT.parent])
def test_load_config_resolves_conf_path_from_repo_root_or_package_root(
    monkeypatch: pytest.MonkeyPatch, cwd: Path
) -> None:
    monkeypatch.chdir(cwd)
    cfg = load_config("conf/default.yaml")
    assert cfg.session.root_dir == PACKAGE_ROOT / "data" / "calibration"


@pytest.mark.parametrize("cwd", [PACKAGE_ROOT, PACKAGE_ROOT.parent])
def test_resolve_session_dir_from_repo_root_or_package_root(
    monkeypatch: pytest.MonkeyPatch, cwd: Path
) -> None:
    monkeypatch.chdir(cwd)
    existing = next((PACKAGE_ROOT / "data" / "calibration").iterdir())
    relative = existing.relative_to(PACKAGE_ROOT)
    assert resolve_session_dir(relative) == existing
