# @package handgrip_analysis._paths
# @brief Path resolution helpers that anchor relative CLI paths to the package root.

"""
Path resolution helpers.

CLI inputs/defaults (``manifest``, ``outdir``, ``filter_config``,
``lsl_bridge_config``, etc.) are conventionally given as paths relative to
``Handgrip_Analysis/``. These helpers let commands run identically whether the
process cwd is ``Handgrip_Analysis/`` itself or the repo root.
"""

from __future__ import annotations

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[2]


# @brief Resolve a relative path expected to already exist, preferring cwd then PACKAGE_ROOT.
# @param path Path supplied by the user or config.
# @return Resolved path: as-is if absolute or cwd-relative exists, else PACKAGE_ROOT-relative if that exists.
def resolve_existing_path(path: str | Path) -> Path:
    """cwd-first, then PACKAGE_ROOT fallback, for inputs expected to exist."""
    p = Path(path)
    if p.is_absolute() or p.exists():
        return p
    candidate = PACKAGE_ROOT / p
    return candidate if candidate.exists() else p


# @brief Anchor a relative output path to PACKAGE_ROOT so outputs land under Handgrip_Analysis/.
# @param path Output path supplied by the user or config.
# @return Resolved path: as-is if absolute, else PACKAGE_ROOT-relative.
def resolve_output_path(path: str | Path) -> Path:
    """Anchor relative output paths to PACKAGE_ROOT."""
    p = Path(path)
    return p if p.is_absolute() else PACKAGE_ROOT / p
