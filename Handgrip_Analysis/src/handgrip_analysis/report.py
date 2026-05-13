from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd

log = logging.getLogger(__name__)


def save_json(path: str | Path, payload: dict[str, Any]) -> None:
    """Write *payload* as indented JSON to *path*."""
    path = Path(path)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
    log.info("save_json: wrote %s", path)


def save_csv(path: str | Path, df: pd.DataFrame) -> None:
    """Write *df* as CSV (no index) to *path*."""
    path = Path(path)
    df.to_csv(path, index=False)
    log.info("save_csv: wrote %s (%d rows)", path, len(df))
