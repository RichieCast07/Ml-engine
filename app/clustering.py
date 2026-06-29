"""
Clustering no supervisado (K-Means) de destinos turisticos por nivel de
afluencia y costo, para distinguir destinos saturados de aquellos con
potencial oculto -- el corazon del objetivo de turismo sostenible del
proyecto.
"""

from functools import lru_cache

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

    # K-Means numera los clusters de forma arbitraria (0, 1, 2...), asi que
    # hay que averiguar cual cluster tiene mas afluencia en promedio para
    # asignarle el nombre correcto ("saturado", "moderado", "potencial_oculto").
    afluencia_promedio_por_cluster = {}
    for cluster_id in sorted(destinos["cluster"].unique()):
        destinos_del_cluster = destinos[destinos["cluster"] == cluster_id]
        afluencia_promedio_por_cluster[cluster_id] = destinos_del_cluster["nivel_afluencia"].mean()

    clusters_ordenados_por_afluencia = sorted(
        afluencia_promedio_por_cluster,
        key=lambda cluster_id: afluencia_promedio_por_cluster[cluster_id],
    )

    mapa_etiquetas = {}
    for posicion, cluster_id in enumerate(clusters_ordenados_por_afluencia):
        mapa_etiquetas[cluster_id] = ETIQUETAS_POR_AFLUENCIA[posicion]

    destinos["cluster_afluencia"] = destinos["cluster"].map(mapa_etiquetas)

    return destinos.drop(columns=["cluster"])


def resumen_clusters() -> dict:
    destinos = entrenar_clusters()

    resumen = {}
    for etiqueta in destinos["cluster_afluencia"].unique():
        grupo = destinos[destinos["cluster_afluencia"] == etiqueta]
        resumen[etiqueta] = {
            "n_destinos": len(grupo),
            "afluencia_promedio": round(grupo["nivel_afluencia"].mean(), 1),
            "costo_promedio": round(grupo["costo_estimado"].mean(), 1),
        }

    return resumen


if __name__ == "__main__":
    pd.set_option("display.width", 120)
    resultado = entrenar_clusters()
    print(resultado[["nombre", "categoria", "nivel_afluencia", "costo_estimado", "cluster_afluencia"]])
    print("\nResumen por cluster:")
    print(resumen_clusters())
