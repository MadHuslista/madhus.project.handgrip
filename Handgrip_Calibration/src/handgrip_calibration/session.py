"""Session-directory and manifest management."""

from __future__ import annotations

import logging
import os
import shutil
import socket
import subprocess
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .config_schema import AppConfig
from .export import ensure_dir

log = logging.getLogger(__name__)


def _safe_git_sha(path: Path) -> str | None:
    """Return the git SHA for *path* when it is inside a git repository.

    The calibration manifest should capture software provenance where possible,
    but it must not fail just because the package is copied outside git.
    """

    try:
        result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=2,
        )
        return result.stdout.strip()
    except Exception:
        return None


@dataclass(frozen=True)
class SessionPaths:
    """Canonical paths produced by a calibration session."""

    root: Path
    manifest: Path
    events: Path
    quality: Path
    target_csv: Path
    reference_csv: Path
    dataset_csv: Path
    fit_json: Path
    report_md: Path
    report_html: Path
    plots_dir: Path
    component_configs_dir: Path
    session_log: Path


class SessionManager:
    """Create and own the session folder structure.

    A calibration session is treated as an immutable data product: raw streams,
    event markers, config snapshots, fitting dataset, and report all live under
    one directory named by a session id.
    """

    def __init__(self, config: AppConfig, *, session_id: str | None = None) -> None:
        self.config = config
        self.session_id = session_id or self.make_session_id()
        root = config.session.root_dir / self.session_id
        self.paths = SessionPaths(
            root=root,
            manifest=root / "session_manifest.yaml",
            events=root / "events.ndjson",
            quality=root / "quality_live.ndjson",
            target_csv=root / "target.csv",
            reference_csv=root / "reference.csv",
            dataset_csv=root / "calibration_dataset.csv",
            fit_json=root / "fit_result.json",
            report_md=root / "calibration_report.md",
            report_html=root / "calibration_report.html",
            plots_dir=root / "plots",
            component_configs_dir=root / "component_configs",
            session_log=root / "session.log",
        )

    @staticmethod
    def make_session_id(prefix: str = "handgrip_cal") -> str:
        """Generate a filesystem-safe session id in local time."""

        return datetime.now().strftime(f"%Y-%m-%d_%H%M%S_{prefix}")

    def create(self, *, extra_manifest: dict[str, Any] | None = None) -> SessionPaths:
        """Create the session directory and write its manifest."""

        ensure_dir(self.paths.root)
        ensure_dir(self.paths.plots_dir)
        ensure_dir(self.paths.component_configs_dir)
        self.copy_component_configs()
        self.write_manifest(extra_manifest=extra_manifest or {})
        log.info("Session directory created: %s", self.paths.root)
        return self.paths

    def manifest_dict(self, *, extra_manifest: dict[str, Any] | None = None) -> dict[str, Any]:
        """Build the session manifest as a plain dictionary."""

        package_root = Path(__file__).resolve().parents[1]
        return {
            "schema": "handgrip_session_manifest.v1",
            "session": {
                "session_id": self.session_id,
                "created_utc": datetime.now(timezone.utc).isoformat(),
                "operator": self.config.session.operator,
                "purpose": self.config.session.purpose,
                "notes": self.config.session.notes,
            },
            "host": {
                "hostname": socket.gethostname(),
                "cwd": os.getcwd(),
                "package_git_sha": _safe_git_sha(package_root),
            },
            "streams": {name: asdict(stream) for name, stream in self.config.streams.items()},
            "markers": asdict(self.config.markers),
            "protocol": asdict(self.config.protocol),
            "quality": asdict(self.config.quality),
            "fit": asdict(self.config.fit),
            "component_config_snapshots": self._component_snapshot_names(),
            "extra": extra_manifest or {},
        }

    def write_manifest(self, *, extra_manifest: dict[str, Any] | None = None) -> None:
        """Write `session_manifest.yaml`."""

        with self.paths.manifest.open("w", encoding="utf-8") as fh:
            yaml.safe_dump(self.manifest_dict(extra_manifest=extra_manifest), fh, sort_keys=False, allow_unicode=True)

    def copy_component_configs(self) -> None:
        """Copy configured component files into the session folder.

        Missing snapshot files are intentionally ignored. This avoids failing a
        calibration run simply because one optional upstream app was not present
        on the current machine.
        """

        for src in self.config.session.copy_component_configs:
            src = src.expanduser()
            if not src.exists():
                continue
            dst = self.paths.component_configs_dir / src.name
            if src.is_dir():
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)

    def _component_snapshot_names(self) -> list[str]:
        if not self.paths.component_configs_dir.exists():
            return []
        return sorted(p.name for p in self.paths.component_configs_dir.iterdir())
