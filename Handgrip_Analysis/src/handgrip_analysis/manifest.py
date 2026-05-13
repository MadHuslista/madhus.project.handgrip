"""Manifest loading and validation for multi-trial handgrip analysis."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd

from .domain import ManifestError, TrialSpec

log = logging.getLogger(__name__)

REQUIRED_COLUMNS = {"stage", "condition", "trial_type", "trial_id", "session_id", "path"}
OPTIONAL_COLUMNS = {"channel", "include", "load_nominal_n", "notes"}

_STAGE_RE = re.compile(r"stage(?P<stage>\d+)")
_TRIAL_RE = re.compile(r"trial(?P<trial>\d+)")
_SESSION_RE = re.compile(r"(?P<session>20\d{6})")


@dataclass(frozen=True, slots=True)
class ManifestIssue:
    """A validation issue that can be reported before execution."""

    severity: str
    row_index: int | None
    message: str

    def to_record(self) -> dict[str, object]:
        return {"severity": self.severity, "row_index": self.row_index, "message": self.message}


def _clean(value: object, default: str = "") -> str:
    if value is None or pd.isna(value):
        return default
    return str(value).strip()


def _parse_bool(value: object, default: bool = True) -> bool:
    if value is None or pd.isna(value):
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "t", "yes", "y", "include", "included"}:
        return True
    if text in {"0", "false", "f", "no", "n", "exclude", "excluded"}:
        return False
    raise ManifestError(f"Invalid boolean value for include: {value!r}")


def _parse_float(value: object) -> float | None:
    if value is None or pd.isna(value) or str(value).strip() == "":
        return None
    return float(value)


def _infer_from_path(path: Path) -> dict[str, str]:
    stem = path.stem
    parts = stem.split("_")
    inferred: dict[str, str] = {}
    if m := _SESSION_RE.search(stem):
        inferred["session_id"] = m.group("session")
    if m := _STAGE_RE.search(stem):
        inferred["stage"] = f"stage{m.group('stage')}"
    if m := _TRIAL_RE.search(stem):
        inferred["trial_id"] = f"trial{m.group('trial')}"
    if "stage" in inferred:
        try:
            stage_idx = parts.index(inferred["stage"])
            trial_idx = next((i for i, p in enumerate(parts) if _TRIAL_RE.fullmatch(p)), len(parts))
            condition = "_".join(parts[stage_idx + 1 : trial_idx])
            if condition:
                inferred["condition"] = condition
                inferred["trial_type"] = condition
        except ValueError:
            pass
    return inferred


def normalize_manifest_frame(df: pd.DataFrame, base_dir: str | Path | None = None) -> pd.DataFrame:
    """
    Normalize current or legacy manifest schemas into the Phase 1 schema.

    Legacy support is intentional to avoid destabilizing the existing library:
    a manifest with ``label`` and ``path`` can still be upgraded by inferring
    stage/session/trial metadata from filenames.
    """
    base = Path(base_dir).resolve() if base_dir is not None else Path.cwd().resolve()
    rows: list[dict[str, object]] = []
    for idx, row in df.iterrows():
        raw_path = Path(_clean(row.get("path")))
        if not raw_path.is_absolute():
            raw_path = (base / raw_path).resolve()
        inferred = _infer_from_path(raw_path)
        label = _clean(row.get("label"))
        stage = _clean(row.get("stage"), inferred.get("stage", ""))
        condition = _clean(row.get("condition"), _clean(row.get("trial_type"), inferred.get("condition", label or raw_path.stem)))
        trial_type = _clean(row.get("trial_type"), inferred.get("trial_type", condition))
        trial_id = _clean(row.get("trial_id"), inferred.get("trial_id", f"trial{idx + 1:02d}"))
        session_id = _clean(row.get("session_id"), inferred.get("session_id", "session_unknown"))
        rows.append(
            {
                "stage": stage,
                "condition": condition,
                "trial_type": trial_type,
                "trial_id": trial_id,
                "session_id": session_id,
                "path": raw_path,
                "channel": _clean(row.get("channel"), "raw"),
                "include": _parse_bool(row.get("include"), True),
                "load_nominal_n": _parse_float(row.get("load_nominal_n")),
                "notes": _clean(row.get("notes")),
            }
        )
    return pd.DataFrame(rows)


def validate_manifest_frame(df: pd.DataFrame) -> list[ManifestIssue]:
    """Return all manifest validation issues without raising immediately."""
    issues: list[ManifestIssue] = []
    missing_cols = REQUIRED_COLUMNS - set(df.columns)
    for col in sorted(missing_cols):
        issues.append(ManifestIssue("error", None, f"Missing required manifest column: {col}"))
    if missing_cols:
        return issues

    identities: set[tuple[str, str, str, str, str]] = set()
    for idx, row in df.iterrows():
        for col in REQUIRED_COLUMNS:
            if col == "path":
                continue
            if not _clean(row.get(col)):
                issues.append(ManifestIssue("error", int(idx), f"Column {col!r} must not be empty"))
        path = Path(row["path"])
        if not path.exists():
            issues.append(ManifestIssue("error", int(idx), f"Capture path does not exist: {path}"))
        identity = (
            _clean(row.get("stage")),
            _clean(row.get("condition")),
            _clean(row.get("trial_type")),
            _clean(row.get("session_id")),
            _clean(row.get("trial_id")),
        )
        if identity in identities:
            issues.append(ManifestIssue("error", int(idx), f"Duplicate trial identity: {identity}"))
        identities.add(identity)
    return issues


def frame_to_trial_specs(df: pd.DataFrame, include_only: bool = True) -> list[TrialSpec]:
    """Convert a normalized manifest frame into ``TrialSpec`` objects."""
    specs: list[TrialSpec] = []
    for _, row in df.iterrows():
        include = _parse_bool(row.get("include"), True)
        if include_only and not include:
            continue
        specs.append(
            TrialSpec(
                stage=_clean(row["stage"]),
                condition=_clean(row["condition"]),
                trial_type=_clean(row["trial_type"]),
                trial_id=_clean(row["trial_id"]),
                session_id=_clean(row["session_id"]),
                path=Path(row["path"]),
                channel=_clean(row.get("channel"), "raw"),
                include=include,
                load_nominal_n=_parse_float(row.get("load_nominal_n")),
                notes=_clean(row.get("notes")),
            )
        )
    return specs


def load_manifest(path: str | Path, include_only: bool = True) -> list[TrialSpec]:
    """Read, normalize, validate, and convert a trial manifest."""
    path = Path(path)
    raw = pd.read_csv(path)
    frame = normalize_manifest_frame(raw, base_dir=path.parent)
    issues = validate_manifest_frame(frame)
    errors = [issue for issue in issues if issue.severity == "error"]
    if errors:
        detail = "; ".join(issue.message for issue in errors[:5])
        if len(errors) > 5:
            detail += f"; ... ({len(errors)} errors total)"
        raise ManifestError(detail)
    specs = frame_to_trial_specs(frame, include_only=include_only)
    log.info("load_manifest: loaded %d included trial(s) from %s", len(specs), path)
    return specs


def filter_trials(
    trials: Sequence[TrialSpec],
    *,
    stage: str | None = None,
    condition: str | None = None,
    trial_type: str | None = None,
) -> list[TrialSpec]:
    """Return trials matching optional stage/condition/trial_type filters."""
    selected = list(trials)
    if stage is not None:
        selected = [t for t in selected if t.stage == stage]
    if condition is not None:
        selected = [t for t in selected if t.condition == condition]
    if trial_type is not None:
        selected = [t for t in selected if t.trial_type == trial_type]
    return selected


def group_by_condition(trials: Iterable[TrialSpec]) -> dict[tuple[str, str], list[TrialSpec]]:
    """Group trials by ``(stage, condition)``."""
    groups: dict[tuple[str, str], list[TrialSpec]] = {}
    for trial in trials:
        groups.setdefault((trial.stage, trial.condition), []).append(trial)
    return groups
