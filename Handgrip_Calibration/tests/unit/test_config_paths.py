from __future__ import annotations

from pathlib import Path

import pytest

from handgrip_calibration.config_schema import (
    PACKAGE_ROOT,
    AppConfig,
    SessionConfig,
    load_config,
    resolve_session_dir,
)
from handgrip_calibration.session import SessionManager


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


# --- SessionManager path resolution tests ---

def _default_config() -> AppConfig:
    return load_config(PACKAGE_ROOT / "conf" / "default.yaml")


def test_session_manager_bare_id_appended_to_root_dir() -> None:
    cfg = _default_config()
    sm = SessionManager(cfg, session_id="my_session_id")
    assert sm.paths.root == cfg.session.root_dir / "my_session_id"
    assert sm.session_id == "my_session_id"


@pytest.mark.parametrize("cwd", [PACKAGE_ROOT, PACKAGE_ROOT.parent])
def test_session_manager_relative_path_no_doubling(
    monkeypatch: pytest.MonkeyPatch, cwd: Path
) -> None:
    monkeypatch.chdir(cwd)
    cfg = _default_config()
    existing = next((PACKAGE_ROOT / "data" / "calibration").iterdir())
    relative = str(existing.relative_to(PACKAGE_ROOT))
    sm = SessionManager(cfg, session_id=relative)
    assert sm.paths.root == existing
    assert sm.session_id == existing.name


def test_session_manager_absolute_path_used_directly() -> None:
    cfg = _default_config()
    existing = next((PACKAGE_ROOT / "data" / "calibration").iterdir())
    sm = SessionManager(cfg, session_id=str(existing))
    assert sm.paths.root == existing
    assert sm.session_id == existing.name
