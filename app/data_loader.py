import csv
from functools import lru_cache
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@lru_cache(maxsize=1)
def cargar_destinos() -> pd.DataFrame:
    ruta_csv = DATA_DIR / "destinos.csv"
    df = pd.read_csv(ruta_csv, encoding="utf-8", dtype={"id": int}, low_memory=False)
    df["categoria"] = df["categoria"].fillna("").astype(str)
    df["categoria"] = df["categoria"].replace("", None)
    # Columnas opcionales del dataset real: coordenadas exactas y foto real
    for col in ("lat", "lng", "foto_url"):
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str).replace("nan", "")
    return df


@lru_cache(maxsize=1)
def cargar_historial_visitas() -> list[list[str]]:
    ruta_csv = DATA_DIR / "historial_visitas.csv"
    transacciones = []
    with open(ruta_csv, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for fila in reader:
            cats = [c.strip() for c in fila["categorias"].split("|") if c.strip()]
            if cats:
                transacciones.append(cats)
    return transacciones
