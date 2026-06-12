"""Tests for cwd-independent path resolution helpers."""

from __future__ import annotations

from pathlib import Path

from handgrip_analysis._paths import PACKAGE_ROOT, resolve_existing_path, resolve_output_path

REPO_ROOT = PACKAGE_ROOT.parent


def test_resolve_existing_path_from_package_root(monkeypatch):
    monkeypatch.chdir(PACKAGE_ROOT)
    resolved = resolve_existing_path("data/manifests/stage2_manifest.csv")
    assert resolved.resolve() == PACKAGE_ROOT / "data/manifests/stage2_manifest.csv"
    assert resolved.exists()


def test_resolve_existing_path_from_repo_root(monkeypatch):
    monkeypatch.chdir(REPO_ROOT)
    resolved = resolve_existing_path("data/manifests/stage2_manifest.csv")
    assert resolved.resolve() == PACKAGE_ROOT / "data/manifests/stage2_manifest.csv"
    assert resolved.exists()


def test_resolve_existing_path_sibling_component_from_both_cwds(monkeypatch):
    expected = REPO_ROOT / "LSL_Bridge/conf/config.yaml"

    monkeypatch.chdir(PACKAGE_ROOT)
    assert resolve_existing_path("../LSL_Bridge/conf/config.yaml").resolve() == expected

    monkeypatch.chdir(REPO_ROOT)
    assert resolve_existing_path("../LSL_Bridge/conf/config.yaml").resolve() == expected


def test_resolve_existing_path_missing_input_falls_back_unchanged(monkeypatch):
    monkeypatch.chdir(REPO_ROOT)
    missing = Path("data/manifests/does_not_exist.csv")
    assert resolve_existing_path(missing) == missing


def test_resolve_output_path_anchors_to_package_root_from_both_cwds(monkeypatch):
    expected = PACKAGE_ROOT / "data/analysis_results/stage2"

    monkeypatch.chdir(PACKAGE_ROOT)
    assert resolve_output_path("data/analysis_results/stage2") == expected

    monkeypatch.chdir(REPO_ROOT)
    assert resolve_output_path("data/analysis_results/stage2") == expected


def test_resolve_output_path_absolute_unchanged(tmp_path):
    abs_path = tmp_path / "out"
    assert resolve_output_path(abs_path) == abs_path
