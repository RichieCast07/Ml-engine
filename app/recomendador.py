"""
Orquesta las 4 tecnicas de mineria de datos descritas en la arquitectura de
Capa 2: filtrado/scoring, clustering K-Means, reglas de asociacion Apriori y
optimizacion de mochila. Toma los parametros que entrega la Capa 1 (NLP) y
devuelve un itinerario concreto basado solo en datos reales del catalogo.
"""

import json
import re
from pathlib import Path

from app.asociacion import categorias_complementarias
from app.clustering import entrenar_clusters
from app.data_loader import cargar_destinos
from app.knapsack import resolver_mochila
from app.schemas import ParametrosViajeIn
from app.texto_utils import normalizar

_COORDS_PATH = Path(__file__).resolve().parent.parent / "data" / "municipio_coords.json"
_MUNICIPIO_COORDS: dict = {}

try:
    with open(_COORDS_PATH, encoding="utf-8") as _f:
        _MUNICIPIO_COORDS = json.load(_f)
except Exception:
    pass

_FOTOS_PATH = Path(__file__).resolve().parent.parent / "data" / "fotos_categorias.json"
_FOTOS_CATEGORIAS: dict = {}

try:
    with open(_FOTOS_PATH, encoding="utf-8") as _f:
        _FOTOS_CATEGORIAS = json.load(_f)
    print(f"[recomendador] fotos_categorias cargadas: {list(_FOTOS_CATEGORIAS.keys())}")
except Exception as _e:
    print(f"[recomendador] ERROR cargando fotos_categorias: {_e}")


def _get_foto(categoria: str | None, dest_id: int) -> str | None:
    fotos = _FOTOS_CATEGORIAS.get(categoria) if categoria else None
    if not fotos:
        return None
    if isinstance(fotos, list):
        return fotos[dest_id % len(fotos)]
    return fotos

BONUS_INTERES_PRINCIPAL = 3.0
BONUS_CATEGORIA_COMPLEMENTARIA = 1.5
BONUS_POTENCIAL_OCULTO = 2.0
PENALIZACION_SATURADO = 1.0

# Los candidatos ya vienen ordenados por score descendente; los primeros
# 150 cubren todos los destinos relevantes. Con n=150, C=500, T=16 la
# tabla DP numpy ocupa ~5 MB y se resuelve en <200 ms.
MAX_CANDIDATOS_KNAPSACK = 150

# Presupuesto por default cuando el usuario no lo especifica (pesos MXN).
# Se elige 2000 como valor tipico de una excursion de un dia en Chiapas.
PRESUPUESTO_DEFAULT = 2000.0

# Techo absoluto de presupuesto que se pasa a la mochila. La restriccion de
# tiempo limita de todas formas cuantos lugares se pueden visitar en un dia,
# por lo que valores mayores no cambian el resultado pero si la memoria usada.
MAX_PRESUPUESTO_DP = 5000.0


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
        patron = normalizar(destino_texto)
        antes = len(destinos)
        destinos = destinos[
            destinos["municipio"].apply(normalizar).str.contains(patron, regex=False)
            | destinos["nombre"].apply(normalizar).str.contains(patron, regex=False)
        ]
        print(f"[recomendador] destino='{destino_texto}' patron='{patron}' {antes}->{len(destinos)} destinos")
    else:
        print(f"[recomendador] destino=None, sin filtro de municipio")

    if interes:
        categorias_aceptadas = {interes} | complementarias
        destinos = destinos[destinos["categoria"].isin(categorias_aceptadas)]

    return destinos


def _filtrar_restaurantes(comida_texto, destino_texto):
    df = cargar_destinos()
    restaurantes = df[df["tipo"] == "restaurante"]

    if destino_texto:
        patron = normalizar(destino_texto)
        coincide_municipio = restaurantes["municipio"].apply(normalizar).str.contains(patron)
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

        municipio = fila["municipio"]
        coords = _MUNICIPIO_COORDS.get(municipio, {})
        categoria_dest = fila["categoria"]
        candidatos.append(
            {
                "id": int(fila["id"]),
                "nombre": fila["nombre"],
                "tipo": "destino",
                "municipio": municipio,
                "categoria": categoria_dest,
                "costo_estimado": float(fila["costo_estimado"]),
                "costo_total_grupo": float(fila["costo_estimado"]) * personas,
                "tiempo_horas": float(fila["tiempo_horas"]),
                "nivel_afluencia": int(fila["nivel_afluencia"]),
                "cluster_afluencia": fila["cluster_afluencia"],
                "lat": coords.get("lat"),
                "lng": coords.get("lng"),
                "foto_principal": _get_foto(categoria_dest, int(fila["id"])),
                "valor": valor,
            }
        )

    for _, fila in restaurantes.iterrows():
        valor = 1.0
        municipio = fila["municipio"]
        coords = _MUNICIPIO_COORDS.get(municipio, {})
        candidatos.append(
            {
                "id": int(fila["id"]),
                "nombre": fila["nombre"],
                "tipo": "restaurante",
                "municipio": municipio,
                "categoria": None,
                "costo_estimado": float(fila["costo_estimado"]),
                "costo_total_grupo": float(fila["costo_estimado"]) * personas,
                "tiempo_horas": float(fila["tiempo_horas"]),
                "nivel_afluencia": int(fila["nivel_afluencia"]),
                "cluster_afluencia": None,
                "lat": coords.get("lat"),
                "lng": coords.get("lng"),
                "foto_principal": _get_foto("restaurante", int(fila["id"])),
                "valor": valor,
            }
        )

    candidatos.sort(key=lambda c: c["valor"], reverse=True)
    candidatos = candidatos[:MAX_CANDIDATOS_KNAPSACK]

    return candidatos, resumen_clusters_candidatos, complementarias_info


def generar_recomendacion(params: ParametrosViajeIn) -> dict:
    candidatos, resumen_clusters_candidatos, complementarias_info = _construir_candidatos(params)

    tiempo_disponible = horas_desde_texto(params.tiempo)

    if params.presupuesto is not None:
        presupuesto_disponible = min(params.presupuesto, MAX_PRESUPUESTO_DP)
    else:
        presupuesto_disponible = PRESUPUESTO_DEFAULT

    itinerario = resolver_mochila(candidatos, presupuesto_disponible, tiempo_disponible)

    for item in itinerario:
        item.pop("valor", None)

    reglas_aplicadas = []
    if params.interes:
        for complementaria in complementarias_info:
            texto_regla = (
                f"{params.interes} -> {complementaria['categoria']} "
                f"(confianza {complementaria['confianza']}, soporte {complementaria['soporte']})"
            )
            reglas_aplicadas.append(texto_regla)

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
