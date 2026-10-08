import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "src"))

PROC, RAW = BASE / "data" / "processed", BASE / "data" / "raw"

import build_dataset  # noqa: E402  (needs src on the path)


@pytest.fixture(scope="session")
def built():
    """The weekly dataset built from the committed raw files by the pipeline's
    own build(), not read back from weekly.csv."""
    return build_dataset.build()


@pytest.fixture(scope="session")
def spot():
    """The raw target series, parsed straight from the EconData export without
    going through any pipeline code."""
    rows = []
    with open(RAW / "econdata_excx135.csv", encoding="utf-8-sig") as fh:
        for line in fh:
            parts = line.rstrip("\n").split(",")
            if len(parts) >= 2 and parts[0][:4].isdigit() and parts[1].strip():
                rows.append((parts[0].strip(), float(parts[1])))
    df = pd.DataFrame(rows, columns=["date", "px"])
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


@pytest.fixture(scope="session")
def chosen():
    """The combination setting frozen on the validation era."""
    cfg = json.load(open(PROC / "validation_metrics.json"))["chosen_config"]
    return cfg["ridge"], cfg["delta"], cfg["theta"]
