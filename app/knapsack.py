"""
Optimizacion tipo mochila (0/1 knapsack) en dos dimensiones: selecciona el
subconjunto de actividades (destinos + restaurantes) que maximiza el valor
total sin exceder ni el presupuesto ni el tiempo disponible.
"""

# Granularidad de tiempo: medias horas, para no perder precision al
# discretizar el tiempo disponible en la tabla de programacion dinamica.
PASOS_POR_HORA = 2

# Escala monetaria: 1 unidad de presupuesto = ESCALA_COSTO pesos.
# Con presupuestos tipicos de 500-5000 pesos esto reduce la dimension C
# de 5000 celdas a 500, achicando la tabla DP 10x y evitando OOM.
ESCALA_COSTO = 10


def resolver_mochila(
    items: list[dict],
    presupuesto_max: float,
    tiempo_max_horas: float,
) -> list[dict]:
    if not items:
        return []

    n = len(items)
    capacidad_costo = max(int(round(presupuesto_max / ESCALA_COSTO)), 0)
    capacidad_tiempo = max(int(round(tiempo_max_horas * PASOS_POR_HORA)), 0)

    pesos_costo = [max(int(round(it["costo_total_grupo"] / ESCALA_COSTO)), 0) for it in items]
    pesos_tiempo = [max(int(round(it["tiempo_horas"] * PASOS_POR_HORA)), 0) for it in items]
    valores = [it["valor"] for it in items]

    # tabla[i][c][t] = mejor valor posible usando los primeros i items,
    # sin pasarse de costo c ni de tiempo t.
    tabla = [
        [[0.0] * (capacidad_tiempo + 1) for _ in range(capacidad_costo + 1)]
        for _ in range(n + 1)
    ]

    for i in range(1, n + 1):
        costo_item = pesos_costo[i - 1]
        tiempo_item = pesos_tiempo[i - 1]
        valor_item = valores[i - 1]

        for c in range(capacidad_costo + 1):
            for t in range(capacidad_tiempo + 1):
                mejor_sin_item = tabla[i - 1][c][t]

                cabe_en_presupuesto = costo_item <= c
                cabe_en_tiempo = tiempo_item <= t
                if cabe_en_presupuesto and cabe_en_tiempo:
                    mejor_con_item = tabla[i - 1][c - costo_item][t - tiempo_item] + valor_item
                    tabla[i][c][t] = max(mejor_sin_item, mejor_con_item)
                else:
                    tabla[i][c][t] = mejor_sin_item

    seleccionados = []
    c, t = capacidad_costo, capacidad_tiempo
    for i in range(n, 0, -1):
        if tabla[i][c][t] != tabla[i - 1][c][t]:
            seleccionados.append(items[i - 1])
            c -= pesos_costo[i - 1]
            t -= pesos_tiempo[i - 1]

    seleccionados.reverse()
    return seleccionados
