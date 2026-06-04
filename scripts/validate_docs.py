#!/usr/bin/env python3
"""
Validate Handgrip Suite documentation links, images, referenced paths, and core contracts.

Default mode is strict full-repository validation.
Use --docs-only when validating a documentation-only snapshot that does not contain source,
config files, or binary image/PDF assets.
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

LINK_RE = re.compile(r"(?<!!)(?:\[[^\]]*\])\(([^)]+)\)")
IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")

D2_SCHEMA = "D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>"
CANONICAL_RS485_CONFIG = "RS485_GUI/config/config.yaml"
STALE_RS485_CONFIGS = ("../RS485_GUI/config.yaml", "RS485_GUI/config.yaml")
DEPRECATED_TERMS = ("HX710B", "stm32f103", "Hacer bascula")
LEGACY_SCHEMA_TERMS = ("D,<seq>", "value_gr")

EXCLUDE_PARTS = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "venv",
}

CANONICAL_PREFIXES = (
    "README.md",
    "docs/",
    "Handgrip_Firmware/README.md",
    "Handgrip_Firmware/docs/",
    "RS485_GUI/README.md",
    "RS485_GUI/docs/",
    "LSL_Bridge/README.md",
    "LSL_Bridge/docs/",
    "LSL_Viewer/README.md",
    "LSL_Viewer/docs/",
    "Handgrip_Calibration/README.md",
    "Handgrip_Calibration/docs/",
    "Handgrip_Analysis/README.md",
    "Handgrip_Analysis/docs/",
    "Handgrip_Calibration/data/calibration/README.md",
    "Handgrip_Analysis/data/analysis_results/README.md",
    "Handgrip_Analysis/outputs/README.md",
    "LSL_Bridge/data/README.md",
    "LSL_Bridge/logs/README.md",
    "RS485_GUI/logs/README.md",
)

ARCHIVE_PREFIXES = (
    "docs/archive/",
)

KNOWN_CONFIG_PATHS = [
    "platformio.ini",
    "Handgrip_Firmware/Core/Inc/config.h",
    "RS485_GUI/config/config.yaml",
    "LSL_Bridge/conf/config.yaml",
    "LSL_Viewer/conf/config.yaml",
    "Handgrip_Calibration/conf/protocol_static_reversible_staircase_v3.yaml",
    "Handgrip_Calibration/conf/protocol_reference_verification.yaml",
    "Handgrip_Calibration/conf/protocol_holdout_verification.yaml",
    "Handgrip_Analysis/conf",
]

REQUIRED_MARKDOWN = [
    "README.md",
    "docs/index.md",
    "docs/system-overview.md",
    "docs/architecture/index.md",
    "docs/architecture/stream-contracts.md",
    "docs/hardware/index.md",
    "docs/troubleshooting/index.md",
    "Handgrip_Firmware/docs/serial-protocol.md",
    "LSL_Bridge/docs/stream-contracts.md",
    "Handgrip_Calibration/docs/protocols.md",
    "Handgrip_Analysis/docs/filter-design.md",
]


@dataclass
class Finding:
    severity: str
    path: str
    message: str


def rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def is_external(target: str) -> bool:
    return target.startswith(("http://", "https://", "mailto:", "tel:"))


def strip_target(target: str) -> str:
    target = target.strip()
    target = target.split("#", 1)[0]
    target = target.split("?", 1)[0]
    return urllib.parse.unquote(target)


def iter_markdown(root: Path, include_archive: bool) -> Iterable[Path]:
    for p in root.rglob("*.md"):
        parts = set(p.relative_to(root).parts)
        if parts & EXCLUDE_PARTS:
            continue
        r = rel(p, root)
        if not include_archive and r.startswith(ARCHIVE_PREFIXES):
            continue
        if is_canonical_path(r) or include_archive:
            yield p


def is_canonical_path(r: str) -> bool:
    if r.startswith(ARCHIVE_PREFIXES):
        return False
    return r == "README.md" or any(r.startswith(prefix) for prefix in CANONICAL_PREFIXES)


def validate_required_markdown(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for r in REQUIRED_MARKDOWN:
        if not (root / r).exists():
            findings.append(Finding("ERROR", r, "required Markdown file is missing"))
    return findings


def resolve_link(source: Path, target: str) -> Path:
    cleaned = strip_target(target)
    return (source.parent / cleaned).resolve()


def validate_links(root: Path, docs_only: bool, include_archive: bool, strict_assets: bool) -> list[Finding]:
    findings: list[Finding] = []
    root_resolved = root.resolve()
    for p in iter_markdown(root, include_archive=include_archive):
        text = p.read_text(encoding="utf-8", errors="replace")
        for regex, kind in [(LINK_RE, "link"), (IMAGE_RE, "image")]:
            for m in regex.finditer(text):
                target = m.group(1).strip()
                if not target or target.startswith("#") or is_external(target):
                    continue
                cleaned = strip_target(target)
                if not cleaned:
                    continue
                q = resolve_link(p, cleaned)
                try:
                    q.relative_to(root_resolved)
                except ValueError:
                    findings.append(Finding("ERROR", rel(p, root), f"{kind} escapes repo root: {target}"))
                    continue
                if not q.exists():
                    is_image_path = q.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
                    if docs_only and not strict_assets and (kind == "image" or is_image_path):
                        findings.append(Finding("WARN", rel(p, root), f"asset missing in docs-only snapshot: {target}"))
                    else:
                        findings.append(Finding("ERROR", rel(p, root), f"missing {kind} target: {target}"))
    return findings


def validate_config_paths(root: Path, docs_only: bool) -> list[Finding]:
    findings: list[Finding] = []
    for r in KNOWN_CONFIG_PATHS:
        p = root / r
        if not p.exists():
            sev = "WARN" if docs_only else "ERROR"
            findings.append(Finding(sev, r, "referenced source/config path missing"))

    conf_dir = root / "Handgrip_Calibration/conf"
    if conf_dir.exists():
        for p in conf_dir.rglob("*.yaml"):
            text = p.read_text(encoding="utf-8", errors="replace")
            if "../RS485_GUI/config.yaml" in text:
                findings.append(
                    Finding("ERROR", rel(p, root), "stale RS485 GUI config snapshot path used in calibration config")
                )
    elif not docs_only:
        findings.append(Finding("ERROR", "Handgrip_Calibration/conf", "calibration config directory missing"))
    return findings


def line_allowed_context(text: str) -> bool:
    low = text.lower()
    allow_words = (
        "legacy",
        "stale",
        "deprecated",
        "not current",
        "must not",
        "do not use",
        "old exact",
        "warning",
        "archive",
        "historical",
        "not canonical",
        "wrong",
        "avoid",
        "instead of",
        "known path issue",
        "known documentation drift",
        "if rg",
        "error:",
        "fail if",
        "guard",
    )
    return any(w in low for w in allow_words)


def validate_content_contracts(root: Path, include_archive: bool) -> list[Finding]:
    findings: list[Finding] = []
    canonical_files = list(iter_markdown(root, include_archive=include_archive))
    combined = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in canonical_files)

    required_terms = [
        D2_SCHEMA,
        "HandgripTarget",
        "HandgripReference",
        "HandgripComponentEvents",
        "HandgripCalibrationMarkers",
        "rs485.measurement.v1",
        CANONICAL_RS485_CONFIG,
        "reference_force_N = f(target_raw_count)",
        "protocol_static_reversible_staircase_v3.yaml",
    ]
    for term in required_terms:
        if term not in combined:
            findings.append(Finding("ERROR", "canonical docs", f"required contract term missing: {term}"))

    for p in canonical_files:
        text = p.read_text(encoding="utf-8", errors="replace")
        r = rel(p, root)
        lines = text.splitlines()
        for i, line in enumerate(lines, 1):
            context = "\n".join(lines[max(0, i - 3) : min(len(lines), i + 2)])
            if any(term in line for term in LEGACY_SCHEMA_TERMS) and not line_allowed_context(context):
                findings.append(
                    Finding(
                        "ERROR",
                        r,
                        f"legacy firmware schema term appears without deprecation context at line {i}: {line.strip()}",
                    )
                )
            if any(term in line for term in STALE_RS485_CONFIGS) and not line_allowed_context(context):
                # In Markdown docs this is a review finding. In source/config files the config-path check above is strict.
                findings.append(
                    Finding(
                        "WARN",
                        r,
                        f"stale RS485 config path mentioned without deprecation context at line {i}: {line.strip()}",
                    )
                )
            if any(term in line for term in DEPRECATED_TERMS) and not line_allowed_context(context):
                findings.append(
                    Finding(
                        "WARN",
                        r,
                        f"deprecated hardware term appears in canonical doc without clear archive/deprecation context at line {i}: {line.strip()}",
                    )
                )

    # Links to deprecated material from canonical docs are hard errors.
    for p in canonical_files:
        text = p.read_text(encoding="utf-8", errors="replace")
        r = rel(p, root)
        for m in LINK_RE.finditer(text):
            target = m.group(1)
            if any(term.lower() in target.lower() for term in ("hx710", "stm32f103", "hacer bascula")):
                findings.append(Finding("ERROR", r, f"canonical doc links to deprecated hardware material: {target}"))

    return findings


def print_findings(findings: list[Finding]) -> int:
    errors = [f for f in findings if f.severity == "ERROR"]
    warnings = [f for f in findings if f.severity == "WARN"]
    for f in findings:
        print(f"{f.severity}: {f.path}: {f.message}")
    print(f"\nValidation summary: {len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".", help="Repository root. Default: current directory.")
    parser.add_argument(
        "--docs-only",
        action="store_true",
        help="Treat missing source/config/image assets as warnings where appropriate.",
    )
    parser.add_argument(
        "--include-archive", action="store_true", help="Also scan docs/archive and legacy Documentation markdown."
    )
    parser.add_argument(
        "--strict-assets", action="store_true", help="Fail missing image assets even in docs-only mode."
    )
    args = parser.parse_args(argv)

    root = Path(args.repo_root).resolve()
    if not root.exists():
        print(f"ERROR: repo root does not exist: {root}", file=sys.stderr)
        return 2

    findings: list[Finding] = []
    findings.extend(validate_required_markdown(root))
    findings.extend(
        validate_links(
            root, docs_only=args.docs_only, include_archive=args.include_archive, strict_assets=args.strict_assets
        )
    )
    findings.extend(validate_config_paths(root, docs_only=args.docs_only))
    findings.extend(validate_content_contracts(root, include_archive=args.include_archive))

    return print_findings(findings)


if __name__ == "__main__":
    raise SystemExit(main())
