"""
Clustering no supervisado (K-Means) de destinos turisticos por nivel de
afluencia y costo, para distinguir destinos saturados de aquellos con
potencial oculto -- el corazon del objetivo de turismo sostenible del
proyecto.
"""

from functools import lru_cache

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from app.data_loader import cargar_destinos

N_CLUSTERS = 3
ETIQUETAS_POR_AFLUENCIA = ["potencial_oculto", "moderado", "saturado"]


@lru_cache(maxsize=1)
def entrenar_clusters() -> pd.DataFrame:
    df = cargar_destinos()
    destinos = df[df["tipo"] == "destino"].copy()

    X = destinos[["nivel_afluencia", "costo_estimado"]].to_numpy(dtype=float)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    kmeans = KMeans(n_clusters=N_CLUSTERS, random_state=42, n_init=10)
    destinos["cluster"] = kmeans.fit_predict(X_scaled)

    # Ordena las etiquetas de cluster por afluencia promedio ascendente,
    # asi el cluster con menor afluencia siempre se llama "potencial_oculto"
    # y el de mayor afluencia siempre "saturado", sin importar el id interno
    # que K-Means les haya asignado en esta corrida.
    orden_clusters = (
        destinos.groupby("cluster")["nivel_afluencia"]
        .mean()
        .sort_values()
        .index.tolist()
    )
    mapa_etiquetas = {
        cluster_id: ETIQUETAS_POR_AFLUENCIA[posicion]
        for posicion, cluster_id in enumerate(orden_clusters)
    }
    destinos["cluster_afluencia"] = destinos["cluster"].map(mapa_etiquetas)

    return destinos.drop(columns=["cluster"])


def resumen_clusters() -> dict:
    destinos = entrenar_clusters()
    resumen = (
        destinos.groupby("cluster_afluencia")
        .agg(
            n_destinos=("id", "count"),
            afluencia_promedio=("nivel_afluencia", "mean"),
            costo_promedio=("costo_estimado", "mean"),
        )
        .round(1)
        .to_dict(orient="index")
    )
    return resumen


if __name__ == "__main__":
    pd.set_option("display.width", 120)
    resultado = entrenar_clusters()
    print(resultado[["nombre", "categoria", "nivel_afluencia", "costo_estimado", "cluster_afluencia"]])
    print("\nResumen por cluster:")
    print(resumen_clusters())
