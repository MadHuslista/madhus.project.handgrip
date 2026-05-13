from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Any

import pandas as pd

log = logging.getLogger(__name__)


def to_jsonable(value: Any) -> Any:
    """Convert numpy/pandas/path values into JSON-serializable objects."""
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(v) for v in value]
    if hasattr(value, "item"):
        try:
            return to_jsonable(value.item())
        except Exception:
            pass
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
    return value


def save_json(path: str | Path, payload: dict[str, Any]) -> None:
    """Write *payload* as indented JSON to *path*."""
    path = Path(path)
    with path.open("w", encoding="utf-8") as f:
        json.dump(to_jsonable(payload), f, indent=2, sort_keys=True)
    log.info("save_json: wrote %s", path)


def save_csv(path: str | Path, df: pd.DataFrame) -> None:
    """Write *df* as CSV (no index) to *path*."""
    path = Path(path)
    df.to_csv(path, index=False)
    log.info("save_csv: wrote %s (%d rows)", path, len(df))
