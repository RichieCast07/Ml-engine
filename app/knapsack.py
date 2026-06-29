"""
Optimizacion tipo mochila (0/1 knapsack) en dos dimensiones: selecciona el
subconjunto de actividades (destinos + restaurantes) que maximiza el valor
total sin exceder ni el presupuesto ni el tiempo disponible.
"""

import numpy as np

# Granularidad de tiempo: medias horas, para no perder precision al
# discretizar el tiempo disponible en la tabla de programacion dinamica.
PASOS_POR_HORA = 2


def resolver_mochila(
    items: list[dict],
    presupuesto_max: float,
    tiempo_max_horas: float,
) -> list[dict]:
    if not items:
        return []

    n = len(items)
    capacidad_costo = max(int(round(presupuesto_max)), 0)
    capacidad_tiempo = max(int(round(tiempo_max_horas * PASOS_POR_HORA)), 0)

    pesos_costo = [max(int(round(it["costo_total_grupo"])), 0) for it in items]
    pesos_tiempo = [max(int(round(it["tiempo_horas"] * PASOS_POR_HORA)), 0) for it in items]
    valores = [it["valor"] for it in items]

    dp = np.zeros((n + 1, capacidad_costo + 1, capacidad_tiempo + 1), dtype=np.float64)

    for i in range(1, n + 1):
        w_costo, w_tiempo, valor = pesos_costo[i - 1], pesos_tiempo[i - 1], valores[i - 1]
        anterior = dp[i - 1]
        dp[i] = anterior
        if w_costo <= capacidad_costo and w_tiempo <= capacidad_tiempo:
            dp[i, w_costo:, w_tiempo:] = np.maximum(
                dp[i, w_costo:, w_tiempo:],
                anterior[: capacidad_costo + 1 - w_costo, : capacidad_tiempo + 1 - w_tiempo] + valor,
            )

    seleccionados = []
    w_costo, w_tiempo = capacidad_costo, capacidad_tiempo
    for i in range(n, 0, -1):
        if dp[i, w_costo, w_tiempo] != dp[i - 1, w_costo, w_tiempo]:
            seleccionados.append(items[i - 1])
            w_costo -= pesos_costo[i - 1]
            w_tiempo -= pesos_tiempo[i - 1]

    seleccionados.reverse()
    return seleccionados
