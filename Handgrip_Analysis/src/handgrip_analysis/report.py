from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


def save_json(path: str | Path, payload: dict[str, Any]) -> None:
    with Path(path).open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)


def save_csv(path: str | Path, df: pd.DataFrame) -> None:
    df.to_csv(path, index=False)
