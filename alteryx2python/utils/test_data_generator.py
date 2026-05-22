from __future__ import annotations

from typing import Any

import pandas as pd


def build_dataframe(rows: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(rows)