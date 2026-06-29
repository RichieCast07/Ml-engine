"""
Reglas de asociacion (Apriori) sobre el historial de categorias co-visitadas,
para sugerir intereses complementarios al que pidio el usuario
(ej. "quienes visitan naturaleza tambien suelen elegir gastronomia").
"""

from functools import lru_cache

import pandas as pd
from mlxtend.frequent_patterns import apriori, association_rules
from mlxtend.preprocessing import TransactionEncoder

from app.data_loader import cargar_historial_visitas

MIN_SUPPORT = 0.08
MIN_CONFIDENCE = 0.4


@lru_cache(maxsize=1)
def entrenar_reglas() -> pd.DataFrame:
    transacciones = cargar_historial_visitas()

    encoder = TransactionEncoder()
    matriz = encoder.fit_transform(transacciones)
    df_encoded = pd.DataFrame(matriz, columns=encoder.columns_)

    frecuentes = apriori(df_encoded, min_support=MIN_SUPPORT, use_colnames=True)
    if frecuentes.empty:
        return pd.DataFrame(columns=["antecedents", "consequents", "support", "confidence", "lift"])

    reglas = association_rules(frecuentes, metric="confidence", min_threshold=MIN_CONFIDENCE)
    return reglas.sort_values("confidence", ascending=False).reset_index(drop=True)


def categorias_complementarias(categoria: str, top_n: int = 3) -> list[dict]:
    """Dada una categoria de interes, regresa las categorias que mas
    frecuentemente se eligen junto a ella, segun las reglas aprendidas."""
    reglas = entrenar_reglas()
    if reglas.empty:
        return []

    coincidencias = reglas[reglas["antecedents"].apply(lambda s: categoria in s)]
    resultado = []
    vistos = set()
    for _, fila in coincidencias.iterrows():
        for consecuente in fila["consequents"]:
            if consecuente == categoria or consecuente in vistos:
                continue
            vistos.add(consecuente)
            resultado.append(
                {
                    "categoria": consecuente,
                    "confianza": round(float(fila["confidence"]), 2),
                    "soporte": round(float(fila["support"]), 2),
                }
            )
        if len(resultado) >= top_n:
            break
    return resultado[:top_n]


if __name__ == "__main__":
    pd.set_option("display.width", 160)
    reglas = entrenar_reglas()
    print(reglas[["antecedents", "consequents", "support", "confidence", "lift"]])
    print("\nComplementarias de 'naturaleza':", categorias_complementarias("naturaleza"))
