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


def _coords_para(fila, municipio: str) -> tuple[float | None, float | None]:
    """Prefiere las coordenadas exactas del CSV; si faltan usa el centroide del municipio."""
    try:
        lat = float(fila["lat"])
        lng = float(fila["lng"])
        if lat and lng:
            return lat, lng
    except (KeyError, TypeError, ValueError):
        pass
    c = _MUNICIPIO_COORDS.get(municipio, {})
    return c.get("lat"), c.get("lng")

_FOTOS_PATH = Path(__file__).resolve().parent.parent / "data" / "fotos_categorias.json"
_FOTOS_CATEGORIAS: dict = {}

try:
    with open(_FOTOS_PATH, encoding="utf-8") as _f:
        _FOTOS_CATEGORIAS = json.load(_f)
    print(f"[recomendador] fotos_categorias cargadas: {list(_FOTOS_CATEGORIAS.keys())}")
except Exception as _e:
    print(f"[recomendador] ERROR cargando fotos_categorias: {_e}")

_FOTOS_TIPO_PATH = Path(__file__).resolve().parent.parent / "data" / "fotos_por_tipo.json"
_FOTOS_POR_TIPO: dict = {}

try:
    with open(_FOTOS_TIPO_PATH, encoding="utf-8") as _f:
        _FOTOS_POR_TIPO = json.load(_f)
    print(f"[recomendador] fotos_por_tipo cargadas: {list(_FOTOS_POR_TIPO.keys())}")
except Exception as _e:
    print(f"[recomendador] ERROR cargando fotos_por_tipo: {_e}")

# Palabras clave en el nombre del destino → tipo de foto temática
_TIPO_KEYWORDS: list[tuple[str, list[str]]] = [
    ("cenote",       ["cenote"]),
    ("cascada",      ["cascada", "catarata", "velo"]),
    ("rio",          ["rio ", "río ", "arroyo", "manantial", "nacimiento", "corriente"]),
    ("laguna",       ["laguna", "lago ", "embalse", "presa "]),
    ("cueva",        ["cueva", "caverna", "gruta", "tunel", "túnel", "sotano", "sótano"]),
    ("barranca",     ["barranca", "cañon", "cañón", "canon "]),
    ("mirador",      ["mirador", "panoram", "vista "]),
    ("cerro",        ["cerro", "sierra", "monte ", "volcan", "volcán", "pico ", "cumbre"]),
    ("arqueologico", ["zona arqueol", "ruinas", "piramide", "pirámide", "prehispan", "maya", "zona maya"]),
    ("sendero",      ["sendero", "senda ", "camino ecol", "vereda", "ruta ecol"]),
    ("bosque",       ["bosque", "selva", "reserva", "ecologico", "ecológico"]),
    ("parque",       ["parque", "jardin", "jardín", "plaza", "zócalo", "zocalo"]),
    ("playa",        ["playa", "costa "]),
    ("reserva",      ["reserva biolog", "area natural", "area proteg"]),
]


def _tipo_desde_nombre(nombre: str) -> str | None:
    n = normalizar(nombre)
    for tipo, keywords in _TIPO_KEYWORDS:
        for kw in keywords:
            if kw in n:
                return tipo
    return None


def _get_foto(categoria: str | None, dest_id: int, nombre: str = "", foto_csv: str = "") -> str | None:
    # Foto real (Google Places) guardada en el CSV → máxima prioridad
    if foto_csv and foto_csv.strip():
        return foto_csv.strip()
    # Foto temática por tipo de lugar (cascada, cueva, etc.)
    tipo = _tipo_desde_nombre(nombre) if nombre else None
    if tipo and tipo in _FOTOS_POR_TIPO:
        fotos = _FOTOS_POR_TIPO[tipo]
        return fotos[dest_id % len(fotos)]
    # Fallback: foto por categoría
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


def _filtrar_destinos(
    intereses: set[str],
    excluidas: set[str],
    destino_texto: str | None,
    complementarias: set[str],
) -> "pd.DataFrame":
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

    # Filtro duro 1: eliminar siempre las categorías que el usuario rechazó,
    # independientemente de lo que Apriori haya sugerido.
    if excluidas:
        antes = len(destinos)
        destinos = destinos[~destinos["categoria"].isin(excluidas)]
        print(f"[recomendador] categorias_excluidas={excluidas} {antes}->{len(destinos)} destinos")

    # Filtro por interés: SOLO las categorías que el usuario pidió.
    # Las complementarias de Apriori NO amplían este filtro — sirven únicamente
    # para dar un bonus de score dentro del pool ya filtrado.
    if intereses:
        destinos = destinos[destinos["categoria"].isin(intereses)]

    return destinos


def _filtrar_restaurantes(comida_texto, destino_texto):
    df = cargar_destinos()
    restaurantes = df[df["tipo"] == "restaurante"]

    if not destino_texto:
        return restaurantes

    patron = normalizar(destino_texto)
    locales = restaurantes[
        restaurantes["municipio"].apply(normalizar).str.contains(patron, regex=False)
    ]
    if not locales.empty:
        return locales

    # Sin restaurantes en el municipio pedido → devuelve todos con flag para
    # que _construir_candidatos les asigne menor valor en el knapsack.
    restaurantes = restaurantes.copy()
    restaurantes["_es_regional"] = True
    return restaurantes


def _construir_candidatos(params: ParametrosViajeIn) -> tuple[list[dict], dict[str, int], list[dict]]:
    personas = params.personas or 1
    intereses = params.set_intereses
    excluidas = set(params.categorias_excluidas)

    # Apriori sobre todos los intereses declarados; las excluidas nunca entran.
    complementarias_info = (
        categorias_complementarias(list(intereses), excluidas=excluidas)
        if intereses else []
    )
    categorias_complementarias_set = {c["categoria"] for c in complementarias_info}

    destinos = _filtrar_destinos(intereses, excluidas, params.destino, categorias_complementarias_set)
    restaurantes = _filtrar_restaurantes(params.comida, params.destino)

    resumen_clusters_candidatos = (
        destinos["cluster_afluencia"].value_counts().to_dict() if not destinos.empty else {}
    )

    candidatos: list[dict] = []

    for _, fila in destinos.iterrows():
        valor = 1.0
        cat = fila["categoria"]
        # Bonus mayor si la categoría coincide con alguno de los intereses declarados.
        if cat in intereses:
            valor += BONUS_INTERES_PRINCIPAL
        elif cat in categorias_complementarias_set:
            valor += BONUS_CATEGORIA_COMPLEMENTARIA
        if fila["cluster_afluencia"] == "potencial_oculto":
            valor += BONUS_POTENCIAL_OCULTO
        elif fila["cluster_afluencia"] == "saturado":
            valor -= PENALIZACION_SATURADO

        municipio = fila["municipio"]
        lat, lng = _coords_para(fila, municipio)
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
                "lat": lat,
                "lng": lng,
                "foto_principal": _get_foto(categoria_dest, int(fila["id"]), str(fila["nombre"]), str(fila.get("foto_url", ""))),
                "valor": valor,
            }
        )

    for _, fila in restaurantes.iterrows():
        es_regional = bool(fila.get("_es_regional", False))
        valor = 0.5 if es_regional else 1.0
        municipio = fila["municipio"]
        lat, lng = _coords_para(fila, municipio)
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
                "lat": lat,
                "lng": lng,
                "foto_principal": _get_foto("restaurante", int(fila["id"]), str(fila["nombre"]), str(fila.get("foto_url", ""))),
                "valor": valor,
            }
        )

    # Separar destinos y restaurantes antes de truncar para garantizar
    # que siempre haya restaurantes en el pool, sin importar cuántos destinos existan.
    destinos_pool = sorted(
        [c for c in candidatos if c["tipo"] == "destino"],
        key=lambda c: c["valor"],
        reverse=True,
    )
    restaurantes_pool = sorted(
        [c for c in candidatos if c["tipo"] == "restaurante"],
        key=lambda c: c["valor"],
        reverse=True,
    )
    candidatos = destinos_pool[: MAX_CANDIDATOS_KNAPSACK - 5] + restaurantes_pool[:5]
    candidatos.sort(key=lambda c: c["valor"], reverse=True)

    return candidatos, resumen_clusters_candidatos, complementarias_info


def _intentar_fallback(
    params: ParametrosViajeIn,
    tiempo_disponible: float,
    presupuesto_disponible: float,
) -> tuple[list[dict], str | None]:
    """
    Intenta filtros progresivamente más amplios cuando el itinerario principal sale vacío.
    Las `categorias_excluidas` se respetan SIEMPRE: el usuario las rechazó
    explícitamente y no deben aparecer aunque los otros filtros se relajen.
    """
    interes_principal = params.interes  # puede ser None

    # Intento 1: misma categoría(s), sin restricción de municipio
    if params.destino and params.set_intereses:
        candidatos, _, _ = _construir_candidatos(params.model_copy(update={"destino": None}))
        resultado = resolver_mochila(candidatos, presupuesto_disponible, tiempo_disponible)
        if resultado:
            cats = ", ".join(params.set_intereses)
            return resultado, (
                f"No encontré destinos de {cats} en {params.destino}. "
                f"Te muestro los mejores lugares de {cats} en todo Chiapas:"
            )

    # Intento 2: mismo municipio, sin restricción de categoría
    # (pero mantenemos categorias_excluidas)
    if params.destino:
        candidatos, _, _ = _construir_candidatos(
            params.model_copy(update={"interes": None, "intereses": [], "comida": None})
        )
        resultado = resolver_mochila(candidatos, presupuesto_disponible, tiempo_disponible)
        if resultado:
            motivo = f"de {interes_principal} " if interes_principal else ""
            return resultado, (
                f"No encontré lugares {motivo}en {params.destino}. "
                f"Te muestro lo que hay disponible en ese municipio:"
            )

    # Intento 3: sin filtro de municipio ni categoría — top Chiapas
    # (categorias_excluidas siguen activas)
    candidatos, _, _ = _construir_candidatos(
        params.model_copy(update={"destino": None, "interes": None, "intereses": [], "comida": None})
    )
    resultado = resolver_mochila(candidatos, presupuesto_disponible, tiempo_disponible)
    if resultado:
        return resultado, (
            "No encontré resultados exactos para tu búsqueda. "
            "Aquí tienes algunos de los mejores destinos de Chiapas:"
        )

    return [], "No encontré destinos disponibles con ese presupuesto y tiempo."


def generar_recomendacion(params: ParametrosViajeIn) -> dict:
    candidatos, resumen_clusters_candidatos, complementarias_info = _construir_candidatos(params)

    tiempo_disponible = horas_desde_texto(params.tiempo)

    if params.presupuesto is not None:
        presupuesto_disponible = min(params.presupuesto, MAX_PRESUPUESTO_DP)
    else:
        presupuesto_disponible = PRESUPUESTO_DEFAULT

    restaurantes_candidatos = [c for c in candidatos if c["tipo"] == "restaurante"]

    # Reservar 1h para comer si el viaje es de medio día o más y hay restaurantes disponibles
    tiempo_para_mochila = tiempo_disponible
    if tiempo_disponible >= 4.0 and restaurantes_candidatos:
        tiempo_para_mochila = tiempo_disponible - 1.0

    itinerario = resolver_mochila(candidatos, presupuesto_disponible, tiempo_para_mochila)

    # Insertar el mejor restaurante disponible si el itinerario no incluye ninguno
    if restaurantes_candidatos and not any(i["tipo"] == "restaurante" for i in itinerario):
        tiempo_usado = sum(i["tiempo_horas"] for i in itinerario)
        costo_usado = sum(i["costo_total_grupo"] for i in itinerario)
        tiempo_libre = tiempo_disponible - tiempo_usado
        presupuesto_libre = presupuesto_disponible - costo_usado
        opciones = [
            r for r in restaurantes_candidatos
            if r["tiempo_horas"] <= tiempo_libre and r["costo_total_grupo"] <= presupuesto_libre
        ]
        if opciones:
            mejor = max(opciones, key=lambda r: r["nivel_afluencia"])
            itinerario.append({k: v for k, v in mejor.items() if k != "valor"})

    mensaje: str | None = None
    es_fallback = False

    hay_destinos = any(i["tipo"] == "destino" for i in itinerario)
    if not itinerario or not hay_destinos:
        itinerario, mensaje = _intentar_fallback(params, tiempo_disponible, presupuesto_disponible)
        es_fallback = len(itinerario) > 0

    for item in itinerario:
        item.pop("valor", None)

    reglas_aplicadas = []
    if params.set_intereses:
        cats = ", ".join(sorted(params.set_intereses))
        for complementaria in complementarias_info:
            texto_regla = (
                f"[{cats}] -> {complementaria['categoria']} "
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
        "mensaje": mensaje,
        "es_fallback": es_fallback,
    }
