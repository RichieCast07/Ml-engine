"""
Orquesta las 4 tecnicas de mineria de datos descritas en la arquitectura de
Capa 2: filtrado/scoring, clustering K-Means, reglas de asociacion Apriori y
optimizacion de mochila. Toma los parametros que entrega la Capa 1 (NLP) y
devuelve un itinerario concreto basado solo en datos reales del catalogo.
"""

import re

from app.asociacion import categorias_complementarias
from app.clustering import entrenar_clusters
from app.data_loader import cargar_destinos
from app.knapsack import resolver_mochila
from app.schemas import ParametrosViajeIn

BONUS_INTERES_PRINCIPAL = 3.0
BONUS_CATEGORIA_COMPLEMENTARIA = 1.5
BONUS_POTENCIAL_OCULTO = 2.0
PENALIZACION_SATURADO = 1.0
BONUS_COMIDA_COINCIDE = 3.0
PRESUPUESTO_SIN_LIMITE_FACTOR = 1.0  # si no hay presupuesto, no se restringe


def horas_desde_texto(tiempo: str | None) -> float:
    """Heuristica simple para convertir frases libres ('medio dia', '2 dias',
    '3 horas') a horas numericas. Es deliberadamente conservadora: ante
    ambiguedad, regresa un valor por defecto razonable en vez de fallar."""
    if not tiempo:
        return 6.0

    texto = tiempo.lower()
    if "medio" in texto:
        return 4.0

    match_horas = re.search(r"(\d+)\s*hora", texto)
    if match_horas:
        return float(match_horas.group(1))

    match_dias = re.search(r"(\d+)\s*d[ií]a", texto)
    if match_dias:
        return float(match_dias.group(1)) * 8.0

    if "dia" in texto or "día" in texto:
        return 8.0

    return 6.0


def _filtrar_destinos(interes, destino_texto, complementarias):
    destinos = entrenar_clusters()

    if destino_texto:
        patron = destino_texto.lower()
        destinos = destinos[
            destinos["municipio"].str.lower().str.contains(patron)
            | destinos["nombre"].str.lower().str.contains(patron)
        ]

    if interes:
        categorias_aceptadas = {interes} | complementarias
        destinos = destinos[destinos["categoria"].isin(categorias_aceptadas)]

    return destinos


def _filtrar_restaurantes(comida_texto, destino_texto):
    df = cargar_destinos()
    restaurantes = df[df["tipo"] == "restaurante"]

    if comida_texto:
        patron = comida_texto.lower()
        restaurantes = restaurantes[restaurantes["tipo_comida"].str.lower().str.contains(patron)]

    if destino_texto:
        patron = destino_texto.lower()
        coincide_municipio = restaurantes["municipio"].str.lower().str.contains(patron)
        if coincide_municipio.any():
            restaurantes = restaurantes[coincide_municipio]

    return restaurantes


def _construir_candidatos(params: ParametrosViajeIn) -> tuple[list[dict], dict[str, int], list[dict]]:
    personas = params.personas or 1
    complementarias_info = categorias_complementarias(params.interes) if params.interes else []
    categorias_complementarias_set = {c["categoria"] for c in complementarias_info}

    destinos = _filtrar_destinos(params.interes, params.destino, categorias_complementarias_set)
    restaurantes = _filtrar_restaurantes(params.comida, params.destino)

    resumen_clusters_candidatos = (
        destinos["cluster_afluencia"].value_counts().to_dict() if not destinos.empty else {}
    )

    candidatos: list[dict] = []

    for _, fila in destinos.iterrows():
        valor = 1.0
        if params.interes and fila["categoria"] == params.interes:
            valor += BONUS_INTERES_PRINCIPAL
        elif fila["categoria"] in categorias_complementarias_set:
            valor += BONUS_CATEGORIA_COMPLEMENTARIA
        if fila["cluster_afluencia"] == "potencial_oculto":
            valor += BONUS_POTENCIAL_OCULTO
        elif fila["cluster_afluencia"] == "saturado":
            valor -= PENALIZACION_SATURADO

        candidatos.append(
            {
                "id": int(fila["id"]),
                "nombre": fila["nombre"],
                "tipo": "destino",
                "municipio": fila["municipio"],
                "categoria": fila["categoria"],
                "tipo_comida": None,
                "costo_estimado": float(fila["costo_estimado"]),
                "costo_total_grupo": float(fila["costo_estimado"]) * personas,
                "tiempo_horas": float(fila["tiempo_horas"]),
                "nivel_afluencia": int(fila["nivel_afluencia"]),
                "cluster_afluencia": fila["cluster_afluencia"],
                "valor": valor,
            }
        )

    for _, fila in restaurantes.iterrows():
        valor = 1.0
        if params.comida and params.comida.lower() in str(fila["tipo_comida"]).lower():
            valor += BONUS_COMIDA_COINCIDE

        candidatos.append(
            {
                "id": int(fila["id"]),
                "nombre": fila["nombre"],
                "tipo": "restaurante",
                "municipio": fila["municipio"],
                "categoria": None,
                "tipo_comida": fila["tipo_comida"],
                "costo_estimado": float(fila["costo_estimado"]),
                "costo_total_grupo": float(fila["costo_estimado"]) * personas,
                "tiempo_horas": float(fila["tiempo_horas"]),
                "nivel_afluencia": int(fila["nivel_afluencia"]),
                "cluster_afluencia": None,
                "valor": valor,
            }
        )

    return candidatos, resumen_clusters_candidatos, complementarias_info


def generar_recomendacion(params: ParametrosViajeIn) -> dict:
    candidatos, resumen_clusters_candidatos, complementarias_info = _construir_candidatos(params)

    tiempo_disponible = horas_desde_texto(params.tiempo)
    presupuesto_disponible = (
        params.presupuesto
        if params.presupuesto is not None
        else sum(c["costo_total_grupo"] for c in candidatos) * PRESUPUESTO_SIN_LIMITE_FACTOR
    )

    itinerario = resolver_mochila(candidatos, presupuesto_disponible, tiempo_disponible)

    for item in itinerario:
        item.pop("valor", None)

    reglas_aplicadas = [
        f"{params.interes} -> {c['categoria']} (confianza {c['confianza']}, soporte {c['soporte']})"
        for c in complementarias_info
    ] if params.interes else []

    return {
        "parametros_entrada": params,
        "itinerario": itinerario,
        "costo_total": round(sum(i["costo_total_grupo"] for i in itinerario), 2),
        "tiempo_total_horas": round(sum(i["tiempo_horas"] for i in itinerario), 2),
        "presupuesto_disponible": params.presupuesto,
        "tiempo_disponible_horas": tiempo_disponible,
        "reglas_asociacion_aplicadas": reglas_aplicadas,
        "resumen_clusters_candidatos": resumen_clusters_candidatos,
    }
