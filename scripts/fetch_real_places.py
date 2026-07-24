"""
Descarga lugares turísticos reales de Chiapas desde OpenStreetMap (Overpass API)
y fotos desde Wikipedia/Wikidata, para reemplazar el dataset sintético de destinos.csv.

Uso (desde la raíz del ml-engine):
    python scripts/fetch_real_places.py

Genera: data/destinos.csv  con columnas
    id, nombre, tipo, municipio, categoria, costo_estimado,
    tiempo_horas, nivel_afluencia, lat, lng, foto_url
"""

import csv
import json
import math
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# ── Rutas ─────────────────────────────────────────────────────────────────────

DATA_DIR    = Path(__file__).resolve().parent.parent / "data"
COORDS_FILE = DATA_DIR / "municipio_coords.json"
OUTPUT_CSV  = DATA_DIR / "destinos.csv"

with open(COORDS_FILE, encoding="utf-8") as f:
    MUNICIPIO_COORDS: dict = json.load(f)

# ── Mapeo de tags OSM → categoría de la app ───────────────────────────────────

def categoria_desde_tags(tags: dict) -> str:
    tourism  = tags.get("tourism", "")
    historic = tags.get("historic", "")
    natural  = tags.get("natural", "")
    leisure  = tags.get("leisure", "")
    amenity  = tags.get("amenity", "")
    sport    = tags.get("sport", "")

    if historic in ("archaeological_site", "ruins", "fort", "castle") or \
       tourism  in ("museum", "gallery") or \
       amenity  in ("place_of_worship", "arts_centre", "community_centre"):
        return "cultura"

    if amenity in ("theatre", "cinema"):
        return "eventos"

    if tourism == "viewpoint":
        return "fotografia"

    if natural in ("waterfall", "spring", "hot_spring", "peak",
                   "cave_entrance", "beach", "cliff"):
        return "naturaleza"

    if leisure in ("nature_reserve", "bird_hide", "swimming_area"):
        return "naturaleza"

    if sport in ("climbing", "hiking", "canoe", "kayaking", "rafting", "cycling"):
        return "aventura"

    if tourism in ("theme_park", "zoo", "aquarium") or \
       leisure in ("playground", "water_park", "miniature_golf"):
        return "familiar"

    if tourism in ("spa", "resort") or amenity == "spa" or \
       leisure in ("spa", "swimming_pool"):
        return "descanso"

    if tourism in ("artwork",):
        return "fotografia"

    if leisure in ("park", "garden") or tourism == "attraction":
        return "naturaleza"

    return "cultura"


# ── Costos y tiempos realistas por categoría (MXN) ────────────────────────────

_COSTO: dict[str, tuple[int, int]] = {
    "naturaleza": (50,  200),
    "cultura":    (30,  120),
    "aventura":   (150, 500),
    "familiar":   (80,  250),
    "descanso":   (200, 800),
    "fotografia": (0,   50),
    "gastronomia":(80,  250),
    "eventos":    (50,  300),
}
_TIEMPO: dict[str, tuple[float, float]] = {
    "naturaleza": (2.0, 4.0),
    "cultura":    (1.0, 2.5),
    "aventura":   (3.0, 6.0),
    "familiar":   (2.0, 4.0),
    "descanso":   (2.0, 4.0),
    "fotografia": (0.5, 1.5),
    "gastronomia":(1.0, 1.5),
    "eventos":    (2.0, 4.0),
}

def _rng(seed: int) -> random.Random:
    return random.Random(seed)

def costo_para(cat: str, seed: int) -> int:
    lo, hi = _COSTO.get(cat, (50, 300))
    return int(_rng(seed).uniform(lo, hi))

def tiempo_para(cat: str, seed: int) -> float:
    lo, hi = _TIEMPO.get(cat, (1.0, 3.0))
    return round(_rng(seed + 9999).uniform(lo, hi), 1)

def afluencia_para(tags: dict, seed: int) -> int:
    if tags.get("wikipedia"):
        return int(_rng(seed).uniform(2000, 10000))
    if tags.get("wikidata"):
        return int(_rng(seed).uniform(800, 3000))
    if tags.get("website") or tags.get("phone"):
        return int(_rng(seed).uniform(300, 1200))
    return int(_rng(seed).uniform(50, 600))


# ── Municipio más cercano ─────────────────────────────────────────────────────

def municipio_cercano(lat: float, lng: float) -> str | None:
    mejor, mejor_d = None, float("inf")
    for nombre, c in MUNICIPIO_COORDS.items():
        d = math.sqrt((c["lat"] - lat) ** 2 + (c["lng"] - lng) ** 2)
        if d < mejor_d:
            mejor_d, mejor = d, nombre
    # Rechazar si está a más de ~150 km del municipio más cercano
    return mejor if mejor_d < 1.5 else None


# ── Foto desde Wikipedia ──────────────────────────────────────────────────────

def foto_wikipedia(wp_tag: str) -> str | None:
    try:
        if ":" in wp_tag:
            lang, title = wp_tag.split(":", 1)
        else:
            lang, title = "es", wp_tag
        title_enc = urllib.parse.quote(title.replace(" ", "_"))
        url = (
            f"https://{lang}.wikipedia.org/w/api.php?action=query"
            f"&titles={title_enc}&prop=pageimages&format=json"
            f"&pithumbsize=800&redirects=1"
        )
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "ExploraChiapas/1.0 (educational; contact: student)"},
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        for page in data.get("query", {}).get("pages", {}).values():
            src = page.get("thumbnail", {}).get("source")
            if src:
                return src
    except Exception:
        pass
    return None


# ── Foto desde Wikidata (propiedad P18 = imagen principal) ───────────────────

def foto_wikidata(wd_id: str) -> str | None:
    """Obtiene la imagen principal (P18) de un elemento Wikidata."""
    try:
        url = (
            f"https://www.wikidata.org/w/api.php?action=wbgetentities"
            f"&ids={urllib.parse.quote(wd_id)}&props=claims&format=json"
        )
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "ExploraChiapas/1.0 (educational; contact: student)"},
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        claims = data.get("entities", {}).get(wd_id, {}).get("claims", {})
        p18 = claims.get("P18", [])
        if p18:
            fname = p18[0]["mainsnak"]["datavalue"]["value"]
            fname_enc = urllib.parse.quote(fname.replace(" ", "_"))
            return f"https://commons.wikimedia.org/wiki/Special:FilePath/{fname_enc}?width=800"
    except Exception:
        pass
    return None


# ── Overpass API ──────────────────────────────────────────────────────────────

_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

def overpass(query: str, intento_max: int = 4) -> list[dict]:
    for i in range(intento_max):
        endpoint = _ENDPOINTS[i % len(_ENDPOINTS)]
        try:
            params = urllib.parse.urlencode({"data": query})
            url    = f"{endpoint}?{params}"
            req    = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "ExploraChiapas/1.0 (educational project; contact: student)",
                    "Accept":     "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.loads(r.read())["elements"]
        except Exception as e:
            print(f"  overpass intento {i+1}/{intento_max} ({endpoint}): {e}")
            if i < intento_max - 1:
                time.sleep(10 * (i + 1))
    return []


_CHIAPAS_AREA = 'area["ISO3166-2"="MX-CHP"]->.ch;'

QUERY_DESTINOS = f"""
[out:json][timeout:180];
{_CHIAPAS_AREA}
(
  node["tourism"~"^(attraction|museum|gallery|viewpoint|zoo|theme_park|aquarium|artwork|camp_site|picnic_site|resort|spa)$"]["name"](area.ch);
  way ["tourism"~"^(attraction|museum|gallery|viewpoint|zoo|theme_park|aquarium|artwork|camp_site|picnic_site|resort|spa)$"]["name"](area.ch);
  node["historic"~"^(monument|memorial|ruins|archaeological_site|castle|church|fort|building)$"]["name"](area.ch);
  way ["historic"~"^(monument|memorial|ruins|archaeological_site|castle|church|fort|building)$"]["name"](area.ch);
  node["natural"~"^(waterfall|spring|hot_spring|peak|cave_entrance|beach|cliff)$"]["name"](area.ch);
  way ["natural"~"^(waterfall|spring|hot_spring|peak|cave_entrance|beach|cliff)$"]["name"](area.ch);
  node["leisure"~"^(nature_reserve|park|garden|bird_hide|water_park|swimming_area|swimming_pool)$"]["name"](area.ch);
  way ["leisure"~"^(nature_reserve|park|garden|bird_hide|water_park|swimming_area|swimming_pool)$"]["name"](area.ch);
  node["amenity"~"^(theatre|cinema|arts_centre|community_centre|spa|place_of_worship)$"]["name"](area.ch);
  way ["amenity"~"^(theatre|cinema|arts_centre|community_centre|spa|place_of_worship)$"]["name"](area.ch);
  node["sport"~"^(climbing|hiking|canoe|kayaking|rafting|cycling)$"]["name"](area.ch);
  way ["sport"~"^(climbing|hiking|canoe|kayaking|rafting|cycling)$"]["name"](area.ch);
);
out center tags;
"""

QUERY_RESTAURANTES = f"""
[out:json][timeout:180];
{_CHIAPAS_AREA}
(
  node["amenity"~"^(restaurant|cafe|fast_food|bar)$"]["name"](area.ch);
  way ["amenity"~"^(restaurant|cafe|fast_food|bar)$"]["name"](area.ch);
);
out center tags;
"""


# ── Procesado de elementos OSM ────────────────────────────────────────────────

def coord_de_elemento(el: dict) -> tuple[float, float] | None:
    if el["type"] == "node":
        return el["lat"], el["lon"]
    if el["type"] == "way" and "center" in el:
        return el["center"]["lat"], el["center"]["lon"]
    return None


def procesar_destinos(elementos: list[dict]) -> list[dict]:
    vistos: set[str] = set()
    filas: list[dict] = []

    for el in elementos:
        tags   = el.get("tags", {})
        nombre = tags.get("name", "").strip()
        if not nombre or nombre in vistos:
            continue
        coords = coord_de_elemento(el)
        if coords is None:
            continue
        lat, lng = coords
        municipio = municipio_cercano(lat, lng)
        if municipio is None:
            continue

        vistos.add(nombre)
        cat = categoria_desde_tags(tags)
        seed = abs(hash(nombre))

        filas.append({
            "nombre":          nombre,
            "tipo":            "destino",
            "municipio":       municipio,
            "categoria":       cat,
            "costo_estimado":  costo_para(cat, seed),
            "tiempo_horas":    tiempo_para(cat, seed),
            "nivel_afluencia": afluencia_para(tags, seed),
            "lat":             round(lat, 6),
            "lng":             round(lng, 6),
            "_wp":             tags.get("wikipedia", ""),
            "_wd":             tags.get("wikidata", ""),
        })

    return filas


def procesar_restaurantes(elementos: list[dict]) -> list[dict]:
    vistos: set[str] = set()
    filas: list[dict] = []

    for el in elementos:
        tags   = el.get("tags", {})
        nombre = tags.get("name", "").strip()
        if not nombre or nombre in vistos:
            continue
        coords = coord_de_elemento(el)
        if coords is None:
            continue
        lat, lng = coords
        municipio = municipio_cercano(lat, lng)
        if municipio is None:
            continue

        vistos.add(nombre)
        seed = abs(hash(nombre))

        filas.append({
            "nombre":          nombre,
            "tipo":            "restaurante",
            "municipio":       municipio,
            "categoria":       "gastronomia",
            "costo_estimado":  costo_para("gastronomia", seed),
            "tiempo_horas":    tiempo_para("gastronomia", seed),
            "nivel_afluencia": afluencia_para(tags, seed),
            "lat":             round(lat, 6),
            "lng":             round(lng, 6),
            "_wp":             tags.get("wikipedia", ""),
            "_wd":             tags.get("wikidata", ""),
        })

    return filas


# ── Fotos: Wikipedia primero, Wikidata como respaldo ─────────────────────────

def enriquecer_fotos(filas: list[dict]) -> list[dict]:
    pendientes = [f for f in filas if not f.get("foto_url") and (f.get("_wp") or f.get("_wd"))]
    print(f"  Buscando fotos para {len(pendientes)} lugares (Wikipedia + Wikidata)...")
    for i, fila in enumerate(pendientes):
        foto = None
        if fila.get("_wp"):
            foto = foto_wikipedia(fila["_wp"])
            time.sleep(0.25)
        if not foto and fila.get("_wd"):
            foto = foto_wikidata(fila["_wd"])
            time.sleep(0.25)
        if foto:
            fila["foto_url"] = foto
        if (i + 1) % 20 == 0:
            print(f"    {i+1}/{len(pendientes)} procesados")
    return filas


# ── Reclasificación por palabras clave en el nombre ──────────────────────────

_KW_AVENTURA = [
    "canopy", "tirolesa", "rappel", "rapel", "escalada", "kayak", "rafting",
    "senderismo", "montaña", "cañon", "cañón", "barranca", "ecoturismo",
    "ciclismo", "bicicleta", "selva", "expedición", "expedicion",
]
_KW_DESCANSO = [
    "balneario", "termal", "termales", "spa", "resort", "retiro",
    "aguas termales", "temazcal", "temascal", "hammam", "jacuzzi",
]
_KW_EVENTOS = [
    "teatro", "auditorio", "foro", "festival", "expo", "feria",
    "centro cultural", "casa de cultura", "casa cultura", "galería",
    "galeria", "cine", "cineplex",
]
_KW_FOTOGRAFIA = [
    "mirador", "miradores", "punto panorámico", "punto panoramico",
    "belvedere", "lookout",
]

def reclasificar(filas: list[dict]) -> list[dict]:
    for fila in filas:
        if fila["tipo"] == "restaurante":
            continue
        nombre_l = fila["nombre"].lower()
        if any(kw in nombre_l for kw in _KW_AVENTURA):
            fila["categoria"] = "aventura"
        elif any(kw in nombre_l for kw in _KW_DESCANSO):
            fila["categoria"] = "descanso"
        elif any(kw in nombre_l for kw in _KW_EVENTOS):
            fila["categoria"] = "eventos"
        elif any(kw in nombre_l for kw in _KW_FOTOGRAFIA):
            fila["categoria"] = "fotografia"
    return filas


# ── Entradas manuales para los lugares más famosos de Chiapas ─────────────────

LUGARES_FAMOSOS = [
    # ── Palenque ──────────────────────────────────────────────────────────────
    {
        "nombre": "Zona Arqueológica de Palenque",
        "tipo": "destino", "municipio": "Palenque", "categoria": "cultura",
        "costo_estimado": 90, "tiempo_horas": 3.5, "nivel_afluencia": 9500,
        "lat": 17.4838, "lng": -92.0458,
        "foto_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/54/Palenque_-_Temple_of_the_Inscriptions.jpg/800px-Palenque_-_Temple_of_the_Inscriptions.jpg",
    },
    {
        "nombre": "Museo de Sitio de Palenque Alberto Ruz",
        "tipo": "destino", "municipio": "Palenque", "categoria": "cultura",
        "costo_estimado": 60, "tiempo_horas": 1.5, "nivel_afluencia": 5200,
        "lat": 17.4820, "lng": -92.0440,
        "foto_url": "",
    },
    # ── Cascadas ──────────────────────────────────────────────────────────────
    {
        "nombre": "Cascada de Agua Azul",
        "tipo": "destino", "municipio": "Tumbala", "categoria": "naturaleza",
        "costo_estimado": 60, "tiempo_horas": 3.0, "nivel_afluencia": 8200,
        "lat": 17.2589, "lng": -92.1131,
        "foto_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/15/Cascadas_de_Agua_Azul.jpg/800px-Cascadas_de_Agua_Azul.jpg",
    },
    {
        "nombre": "Cascada Misol-Ha",
        "tipo": "destino", "municipio": "Tumbala", "categoria": "naturaleza",
        "costo_estimado": 50, "tiempo_horas": 1.5, "nivel_afluencia": 6800,
        "lat": 17.3577, "lng": -92.0998,
        "foto_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4e/Misol-Ha_waterfall.jpg/800px-Misol-Ha_waterfall.jpg",
    },
    {
        "nombre": "Cascada El Chiflón",
        "tipo": "destino", "municipio": "Tzimol", "categoria": "naturaleza",
        "costo_estimado": 80, "tiempo_horas": 3.0, "nivel_afluencia": 7000,
        "lat": 16.0894, "lng": -92.3006,
        "foto_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/ee/El_Chifl%C3%B3n.jpg/800px-El_Chifl%C3%B3n.jpg",
    },
    {
        "nombre": "Cascada Velo de Novia",
        "tipo": "destino", "municipio": "Tzimol", "categoria": "naturaleza",
        "costo_estimado": 80, "tiempo_horas": 2.0, "nivel_afluencia": 5500,
        "lat": 16.086, "lng": -92.295,
        "foto_url": "",
    },
    {
        "nombre": "Cascadas de Roberto Barrios",
        "tipo": "destino", "municipio": "Palenque", "categoria": "naturaleza",
        "costo_estimado": 50, "tiempo_horas": 2.5, "nivel_afluencia": 4800,
        "lat": 17.5550, "lng": -92.1430,
        "foto_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c5/Roberto_Barrios_waterfall.jpg/800px-Roberto_Barrios_waterfall.jpg",
    },
    {
        "nombre": "Cascada Las Golondrinas",
        "tipo": "destino", "municipio": "Ocosingo", "categoria": "naturaleza",
        "costo_estimado": 100, "tiempo_horas": 4.0, "nivel_afluencia": 3500,
        "lat": 17.008, "lng": -91.720,
        "foto_url": "",
    },
    # ── Cañón del Sumidero ────────────────────────────────────────────────────
    {
        "nombre": "Cañón del Sumidero",
        "tipo": "destino", "municipio": "Chiapa de Corzo", "categoria": "naturaleza",
        "costo_estimado": 180, "tiempo_horas": 2.5, "nivel_afluencia": 9000,
        "lat": 16.8514, "lng": -93.0761,
        "foto_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/06/Canyon_del_Sumidero.jpg/800px-Canyon_del_Sumidero.jpg",
    },
    {
        "nombre": "Mirador Cañón del Sumidero",
        "tipo": "destino", "municipio": "Tuxtla Gutierrez", "categoria": "fotografia",
        "costo_estimado": 30, "tiempo_horas": 1.0, "nivel_afluencia": 7200,
        "lat": 16.9034, "lng": -93.0489,
        "foto_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/06/Canyon_del_Sumidero.jpg/800px-Canyon_del_Sumidero.jpg",
    },
    {
        "nombre": "Parque Nacional Cañón del Sumidero",
        "tipo": "destino", "municipio": "Chiapa de Corzo", "categoria": "naturaleza",
        "costo_estimado": 50, "tiempo_horas": 4.0, "nivel_afluencia": 8500,
        "lat": 16.870, "lng": -93.068,
        "foto_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/06/Canyon_del_Sumidero.jpg/800px-Canyon_del_Sumidero.jpg",
    },
    # ── Lagos de Montebello ───────────────────────────────────────────────────
    {
        "nombre": "Lagos de Montebello",
        "tipo": "destino", "municipio": "La Trinitaria", "categoria": "naturaleza",
        "costo_estimado": 50, "tiempo_horas": 4.0, "nivel_afluencia": 7500,
        "lat": 16.1119, "lng": -91.7219,
        "foto_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3c/Lagunas_de_Montebello_Chiapas.jpg/800px-Lagunas_de_Montebello_Chiapas.jpg",
    },
    {
        "nombre": "Parque Nacional Lagunas de Montebello",
        "tipo": "destino", "municipio": "La Trinitaria", "categoria": "aventura",
        "costo_estimado": 60, "tiempo_horas": 5.0, "nivel_afluencia": 7800,
        "lat": 16.0836, "lng": -91.7278,
        "foto_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3c/Lagunas_de_Montebello_Chiapas.jpg/800px-Lagunas_de_Montebello_Chiapas.jpg",
    },
    # ── San Cristóbal de las Casas ────────────────────────────────────────────
    {
        "nombre": "Centro Histórico de San Cristóbal de las Casas",
        "tipo": "destino", "municipio": "San Cristobal de las Casas", "categoria": "cultura",
        "costo_estimado": 0, "tiempo_horas": 3.0, "nivel_afluencia": 9800,
        "lat": 16.7370, "lng": -92.6376,
        "foto_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/24/San_Cristobal_de_las_Casas_Cathedral.jpg/800px-San_Cristobal_de_las_Casas_Cathedral.jpg",
    },
    {
        "nombre": "Templo de Santo Domingo de Guzmán",
        "tipo": "destino", "municipio": "San Cristobal de las Casas", "categoria": "cultura",
        "costo_estimado": 0, "tiempo_horas": 1.0, "nivel_afluencia": 9200,
        "lat": 16.7397, "lng": -92.6383,
        "foto_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/90/Templo_de_Santo_Domingo%2C_San_Cristobal_de_las_Casas.jpg/800px-Templo_de_Santo_Domingo%2C_San_Cristobal_de_las_Casas.jpg",
    },
    {
        "nombre": "Mercado de Artesanías de San Cristóbal",
        "tipo": "destino", "municipio": "San Cristobal de las Casas", "categoria": "cultura",
        "costo_estimado": 0, "tiempo_horas": 1.5, "nivel_afluencia": 8000,
        "lat": 16.7360, "lng": -92.6370,
        "foto_url": "",
    },
    {
        "nombre": "Museo Na Bolom",
        "tipo": "destino", "municipio": "San Cristobal de las Casas", "categoria": "cultura",
        "costo_estimado": 75, "tiempo_horas": 1.5, "nivel_afluencia": 4200,
        "lat": 16.7449, "lng": -92.6338,
        "foto_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c2/Na_Bolom_Museum.jpg/800px-Na_Bolom_Museum.jpg",
    },
    # ── Zona Selva / Mayas ────────────────────────────────────────────────────
    {
        "nombre": "Lago de Miramar",
        "tipo": "destino", "municipio": "Ocosingo", "categoria": "naturaleza",
        "costo_estimado": 120, "tiempo_horas": 5.0, "nivel_afluencia": 4500,
        "lat": 16.4147, "lng": -91.7978,
        "foto_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/87/Lago_Miramar_Chiapas.jpg/800px-Lago_Miramar_Chiapas.jpg",
    },
    {
        "nombre": "Selva Lacandona — Río Lacanjá",
        "tipo": "destino", "municipio": "Ocosingo", "categoria": "aventura",
        "costo_estimado": 350, "tiempo_horas": 6.0, "nivel_afluencia": 3800,
        "lat": 16.7500, "lng": -91.0500,
        "foto_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e5/Lacandon_jungle.jpg/800px-Lacandon_jungle.jpg",
    },
    {
        "nombre": "Yaxchilán Zona Arqueológica",
        "tipo": "destino", "municipio": "Ocosingo", "categoria": "cultura",
        "costo_estimado": 85, "tiempo_horas": 3.0, "nivel_afluencia": 5200,
        "lat": 16.8972, "lng": -90.9639,
        "foto_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/13/Yaxchilan-estructura33.jpg/800px-Yaxchilan-estructura33.jpg",
    },
    {
        "nombre": "Bonampak Zona Arqueológica",
        "tipo": "destino", "municipio": "Ocosingo", "categoria": "cultura",
        "costo_estimado": 85, "tiempo_horas": 2.5, "nivel_afluencia": 4800,
        "lat": 16.7019, "lng": -91.0656,
        "foto_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/44/Bonampak_murals.jpg/800px-Bonampak_murals.jpg",
    },
    {
        "nombre": "Comunidad Lacandona de Naha",
        "tipo": "destino", "municipio": "Ocosingo", "categoria": "cultura",
        "costo_estimado": 150, "tiempo_horas": 4.0, "nivel_afluencia": 2000,
        "lat": 16.970, "lng": -91.580,
        "foto_url": "",
    },
    # ── Tuxtla Gutiérrez ──────────────────────────────────────────────────────
    {
        "nombre": "Zoológico Regional Miguel Álvarez del Toro (ZooMAT)",
        "tipo": "destino", "municipio": "Tuxtla Gutierrez", "categoria": "familiar",
        "costo_estimado": 50, "tiempo_horas": 3.0, "nivel_afluencia": 8500,
        "lat": 16.7191, "lng": -93.1295,
        "foto_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7e/Jaguar_at_ZooMAT.jpg/800px-Jaguar_at_ZooMAT.jpg",
    },
    {
        "nombre": "Parque Madero y Museo Regional de Chiapas",
        "tipo": "destino", "municipio": "Tuxtla Gutierrez", "categoria": "cultura",
        "costo_estimado": 30, "tiempo_horas": 2.0, "nivel_afluencia": 5500,
        "lat": 16.7529, "lng": -93.1060,
        "foto_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b0/Museo_Regional_de_Chiapas.jpg/800px-Museo_Regional_de_Chiapas.jpg",
    },
    {
        "nombre": "Teatro de la Ciudad Emilio Rabasa",
        "tipo": "destino", "municipio": "Tuxtla Gutierrez", "categoria": "eventos",
        "costo_estimado": 150, "tiempo_horas": 2.5, "nivel_afluencia": 4000,
        "lat": 16.7520, "lng": -93.1152,
        "foto_url": "",
    },
    # ── Comitán / La Trinitaria ───────────────────────────────────────────────
    {
        "nombre": "Zona Arqueológica Chinkultic",
        "tipo": "destino", "municipio": "La Trinitaria", "categoria": "cultura",
        "costo_estimado": 55, "tiempo_horas": 2.0, "nivel_afluencia": 3500,
        "lat": 16.1214, "lng": -91.8275,
        "foto_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8c/Chinkultic_archaeological_zone.jpg/800px-Chinkultic_archaeological_zone.jpg",
    },
    {
        "nombre": "Plaza Central de Comitán",
        "tipo": "destino", "municipio": "Comitan de Dominguez", "categoria": "cultura",
        "costo_estimado": 0, "tiempo_horas": 1.5, "nivel_afluencia": 6000,
        "lat": 16.2558, "lng": -92.1336,
        "foto_url": "",
    },
    {
        "nombre": "Museo Belisario Domínguez de Comitán",
        "tipo": "destino", "municipio": "Comitan de Dominguez", "categoria": "cultura",
        "costo_estimado": 40, "tiempo_horas": 1.5, "nivel_afluencia": 3200,
        "lat": 16.2568, "lng": -92.1338,
        "foto_url": "",
    },
    # ── Volcán Tacaná / Soconusco ─────────────────────────────────────────────
    {
        "nombre": "Volcán Tacaná",
        "tipo": "destino", "municipio": "Unión Juárez", "categoria": "aventura",
        "costo_estimado": 200, "tiempo_horas": 8.0, "nivel_afluencia": 2500,
        "lat": 15.1317, "lng": -92.1094,
        "foto_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4b/Volcan_Tacana.jpg/800px-Volcan_Tacana.jpg",
    },
    {
        "nombre": "Café Cacahoatán — Recorrido de Cafetales",
        "tipo": "destino", "municipio": "Cacahoatán", "categoria": "cultura",
        "costo_estimado": 120, "tiempo_horas": 3.0, "nivel_afluencia": 1800,
        "lat": 14.984, "lng": -92.159,
        "foto_url": "",
    },
    # ── Chiapa de Corzo ───────────────────────────────────────────────────────
    {
        "nombre": "Zona Arqueológica Chiapa de Corzo",
        "tipo": "destino", "municipio": "Chiapa de Corzo", "categoria": "cultura",
        "costo_estimado": 55, "tiempo_horas": 1.5, "nivel_afluencia": 4200,
        "lat": 16.7046, "lng": -93.0178,
        "foto_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/ef/Chiapa_de_Corzo_zona_arqueologica.jpg/800px-Chiapa_de_Corzo_zona_arqueologica.jpg",
    },
    {
        "nombre": "La Pila de Chiapa de Corzo",
        "tipo": "destino", "municipio": "Chiapa de Corzo", "categoria": "cultura",
        "costo_estimado": 0, "tiempo_horas": 0.5, "nivel_afluencia": 5000,
        "lat": 16.7072, "lng": -93.0143,
        "foto_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1f/Fuente_colonial_de_Chiapa_de_Corzo.jpg/800px-Fuente_colonial_de_Chiapa_de_Corzo.jpg",
    },
    # ── Ámbar / artesanías ────────────────────────────────────────────────────
    {
        "nombre": "Minas de Ámbar de Simojovel",
        "tipo": "destino", "municipio": "Simojovel", "categoria": "cultura",
        "costo_estimado": 80, "tiempo_horas": 2.0, "nivel_afluencia": 2800,
        "lat": 17.130, "lng": -92.720,
        "foto_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ac/Amber_Simojovel.jpg/800px-Amber_Simojovel.jpg",
    },
    # ── Balnearios / descanso ─────────────────────────────────────────────────
    {
        "nombre": "Balneario Agua Clara",
        "tipo": "destino", "municipio": "Salto de Agua", "categoria": "descanso",
        "costo_estimado": 80, "tiempo_horas": 3.5, "nivel_afluencia": 6000,
        "lat": 17.5714, "lng": -92.4019,
        "foto_url": "",
    },
    {
        "nombre": "Balneario El Paraíso de Berriozabal",
        "tipo": "destino", "municipio": "Berriozabal", "categoria": "descanso",
        "costo_estimado": 100, "tiempo_horas": 3.0, "nivel_afluencia": 4500,
        "lat": 16.797, "lng": -93.271,
        "foto_url": "",
    },
    {
        "nombre": "Aguas Termales de Ocosingo",
        "tipo": "destino", "municipio": "Ocosingo", "categoria": "descanso",
        "costo_estimado": 150, "tiempo_horas": 2.5, "nivel_afluencia": 2000,
        "lat": 17.091, "lng": -92.106,
        "foto_url": "",
    },
    # ── Catazajá ──────────────────────────────────────────────────────────────
    {
        "nombre": "Laguna del Catazajá",
        "tipo": "destino", "municipio": "Catazajá", "categoria": "naturaleza",
        "costo_estimado": 60, "tiempo_horas": 3.0, "nivel_afluencia": 3000,
        "lat": 17.688, "lng": -92.075,
        "foto_url": "",
    },
    # ── Marqués de Comillas / Reservas ────────────────────────────────────────
    {
        "nombre": "Reserva de la Biósfera Montes Azules",
        "tipo": "destino", "municipio": "Marqués de Comillas", "categoria": "naturaleza",
        "costo_estimado": 250, "tiempo_horas": 6.0, "nivel_afluencia": 1500,
        "lat": 16.266, "lng": -90.839,
        "foto_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e5/Lacandon_jungle.jpg/800px-Lacandon_jungle.jpg",
    },
    {
        "nombre": "Ecoturismo Río Lacantún",
        "tipo": "destino", "municipio": "Marqués de Comillas", "categoria": "aventura",
        "costo_estimado": 300, "tiempo_horas": 5.0, "nivel_afluencia": 1200,
        "lat": 16.200, "lng": -90.900,
        "foto_url": "",
    },
    {
        "nombre": "Reserva de la Biósfera Selva El Ocote",
        "tipo": "destino", "municipio": "Ocozocoautla", "categoria": "aventura",
        "costo_estimado": 180, "tiempo_horas": 5.0, "nivel_afluencia": 2200,
        "lat": 16.860, "lng": -93.710,
        "foto_url": "",
    },
    # ── Costa / Tonalá ────────────────────────────────────────────────────────
    {
        "nombre": "Playa de Tonalá — La Encrucijada",
        "tipo": "destino", "municipio": "Tonala", "categoria": "naturaleza",
        "costo_estimado": 80, "tiempo_horas": 4.0, "nivel_afluencia": 4000,
        "lat": 15.680, "lng": -93.450,
        "foto_url": "",
    },
    {
        "nombre": "Reserva de la Biósfera La Encrucijada",
        "tipo": "destino", "municipio": "Acapetahua", "categoria": "naturaleza",
        "costo_estimado": 100, "tiempo_horas": 4.0, "nivel_afluencia": 2500,
        "lat": 15.240, "lng": -92.740,
        "foto_url": "",
    },
    # ── Tzotzil / comunidades indígenas ───────────────────────────────────────
    {
        "nombre": "Templo de San Juan Chamula",
        "tipo": "destino", "municipio": "San Juan Chamula", "categoria": "cultura",
        "costo_estimado": 30, "tiempo_horas": 1.5, "nivel_afluencia": 7500,
        "lat": 16.7905, "lng": -92.6892,
        "foto_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/df/San_Juan_Chamula_church.jpg/800px-San_Juan_Chamula_church.jpg",
    },
    {
        "nombre": "Zinacantán — Pueblo Tzotzil",
        "tipo": "destino", "municipio": "Zinacantlan", "categoria": "cultura",
        "costo_estimado": 50, "tiempo_horas": 2.0, "nivel_afluencia": 5000,
        "lat": 16.767, "lng": -92.721,
        "foto_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/70/Zinacantan_textiles.jpg/800px-Zinacantan_textiles.jpg",
    },
    {
        "nombre": "Amatenango del Valle — Alfarería Tzeltal",
        "tipo": "destino", "municipio": "Amatenango del Valle", "categoria": "cultura",
        "costo_estimado": 40, "tiempo_horas": 1.5, "nivel_afluencia": 3000,
        "lat": 16.480, "lng": -92.400,
        "foto_url": "",
    },
    # ── Grutas ────────────────────────────────────────────────────────────────
    {
        "nombre": "Grutas de Rancho Nuevo",
        "tipo": "destino", "municipio": "San Cristobal de las Casas", "categoria": "naturaleza",
        "costo_estimado": 60, "tiempo_horas": 1.5, "nivel_afluencia": 5000,
        "lat": 16.6791, "lng": -92.5900,
        "foto_url": "",
    },
    {
        "nombre": "Cueva del Jaguar — Ocosingo",
        "tipo": "destino", "municipio": "Ocosingo", "categoria": "aventura",
        "costo_estimado": 120, "tiempo_horas": 3.0, "nivel_afluencia": 1500,
        "lat": 17.050, "lng": -92.100,
        "foto_url": "",
    },
]


def agregar_famosos(filas: list[dict]) -> list[dict]:
    nombres_existentes = {f["nombre"].lower() for f in filas}
    nuevos = 0
    for lugar in LUGARES_FAMOSOS:
        if lugar["nombre"].lower() not in nombres_existentes:
            filas.append({**lugar, "_wp": "", "_wd": ""})
            nuevos += 1
    print(f"  {nuevos} lugares famosos añadidos manualmente")
    return filas


# ── CSV final ─────────────────────────────────────────────────────────────────

COLUMNAS = [
    "id", "nombre", "tipo", "municipio", "categoria",
    "costo_estimado", "tiempo_horas", "nivel_afluencia",
    "lat", "lng", "foto_url",
]

def escribir_csv(filas: list[dict]) -> None:
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNAS)
        writer.writeheader()
        for i, fila in enumerate(filas, start=1):
            writer.writerow({
                "id":             i,
                "nombre":         fila["nombre"],
                "tipo":           fila["tipo"],
                "municipio":      fila["municipio"],
                "categoria":      fila["categoria"],
                "costo_estimado": fila["costo_estimado"],
                "tiempo_horas":   fila["tiempo_horas"],
                "nivel_afluencia":fila["nivel_afluencia"],
                "lat":            fila["lat"],
                "lng":            fila["lng"],
                "foto_url":       fila.get("foto_url", ""),
            })
    print(f"\nCSV generado: {OUTPUT_CSV} ({len(filas)} filas)")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=== ExploraChiapas — Generación de dataset real ===\n")

    print("1/4  Descargando destinos turísticos de OpenStreetMap...")
    elementos_destinos = overpass(QUERY_DESTINOS)
    print(f"     {len(elementos_destinos)} elementos recibidos")

    print("2/4  Descargando restaurantes de OpenStreetMap...")
    elementos_restaurantes = overpass(QUERY_RESTAURANTES)
    print(f"     {len(elementos_restaurantes)} elementos recibidos")

    print("3/4  Procesando y asignando categorías...")
    destinos     = procesar_destinos(elementos_destinos)
    restaurantes = procesar_restaurantes(elementos_restaurantes)
    destinos     = reclasificar(destinos)
    destinos     = agregar_famosos(destinos)
    todas        = destinos + restaurantes
    print(f"     {len(destinos)} destinos, {len(restaurantes)} restaurantes → {len(todas)} total")

    print("4/4  Obteniendo fotos (Wikipedia + Wikidata)...")
    todas = enriquecer_fotos(todas)
    con_foto = sum(1 for f in todas if f.get("foto_url"))
    print(f"     {con_foto} lugares con foto ({con_foto*100//len(todas)}%)")

    escribir_csv(todas)

    from collections import Counter
    cats  = Counter(f["categoria"] for f in todas)
    munis = Counter(f["municipio"] for f in todas)
    print("\n── Distribución por categoría ──")
    for cat, n in sorted(cats.items(), key=lambda x: -x[1]):
        print(f"   {cat:15s}: {n}")
    print("\n── Municipios con más lugares ──")
    for muni, n in munis.most_common(15):
        print(f"   {muni:40s}: {n}")


if __name__ == "__main__":
    main()
