import json
from functools import lru_cache
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@lru_cache(maxsize=1)
def cargar_destinos() -> pd.DataFrame:
    raw = json.loads((DATA_DIR / "destinos.json").read_text(encoding="utf-8"))
    return pd.DataFrame(raw)


@lru_cache(maxsize=1)
def cargar_historial_visitas() -> list[list[str]]:
    return json.loads((DATA_DIR / "historial_visitas.json").read_text(encoding="utf-8"))
