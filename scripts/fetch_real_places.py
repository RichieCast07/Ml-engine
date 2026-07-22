"""
Descarga lugares turísticos reales de Chiapas desde OpenStreetMap (Overpass API)
y fotos desde Wikipedia, para reemplazar el dataset sintético de destinos.csv.

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

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

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
       amenity  == "place_of_worship":
        return "cultura"

    if tourism == "viewpoint":
        return "fotografia"

    if natural in ("waterfall", "spring", "hot_spring", "peak",
                   "cave_entrance", "beach", "cliff"):
        return "naturaleza"

    if leisure in ("nature_reserve", "bird_hide"):
        return "naturaleza"

    if sport in ("climbing", "hiking", "canoe", "kayaking", "rafting"):
        return "aventura"

    if tourism in ("theme_park", "zoo", "aquarium") or \
       leisure in ("playground", "water_park", "miniature_golf"):
        return "familiar"

    if tourism in ("spa", "resort") or amenity == "spa":
        return "descanso"

    if tourism in ("artwork",):
        return "fotografia"

    # Parques y atracciones generales → naturaleza
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


# ISO 3166-2 de Chiapas — más fiable que buscar por nombre
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
  node["leisure"~"^(nature_reserve|park|garden|bird_hide|water_park)$"]["name"](area.ch);
  way ["leisure"~"^(nature_reserve|park|garden|bird_hide|water_park)$"]["name"](area.ch);
);
out center tags;
"""

QUERY_RESTAURANTES = f"""
[out:json][timeout:180];
{_CHIAPAS_AREA}
(
  node["amenity"~"^(restaurant|cafe)$"]["name"](area.ch);
  way ["amenity"~"^(restaurant|cafe)$"]["name"](area.ch);
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
            "nombre":        nombre,
            "tipo":          "destino",
            "municipio":     municipio,
            "categoria":     cat,
            "costo_estimado":costo_para(cat, seed),
            "tiempo_horas":  tiempo_para(cat, seed),
            "nivel_afluencia": afluencia_para(tags, seed),
            "lat":           round(lat, 6),
            "lng":           round(lng, 6),
            "_wp":           tags.get("wikipedia", ""),
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
            "nombre":         nombre,
            "tipo":           "restaurante",
            "municipio":      municipio,
            "categoria":      "gastronomia",
            "costo_estimado": costo_para("gastronomia", seed),
            "tiempo_horas":   tiempo_para("gastronomia", seed),
            "nivel_afluencia":afluencia_para(tags, seed),
            "lat":            round(lat, 6),
            "lng":            round(lng, 6),
            "_wp":            tags.get("wikipedia", ""),
        })

    return filas


# ── Fotos Wikipedia (solo para lugares con tag wikipedia) ─────────────────────

def enriquecer_fotos(filas: list[dict]) -> list[dict]:
    con_wp = [f for f in filas if f["_wp"]]
    print(f"  Buscando fotos en Wikipedia para {len(con_wp)} lugares...")
    for i, fila in enumerate(con_wp):
        foto = foto_wikipedia(fila["_wp"])
        if foto:
            fila["foto_url"] = foto
        if (i + 1) % 10 == 0:
            print(f"    {i+1}/{len(con_wp)} procesados")
        time.sleep(0.3)  # respetar rate limit de Wikipedia
    return filas


# ── Reclasificación por palabras clave en el nombre ──────────────────────────
# OSM no siempre tiene las etiquetas correctas; el nombre del lugar
# da pistas más confiables para aventura, descanso y eventos.

_KW_AVENTURA = [
    "canopy", "tirolesa", "rappel", "escalada", "kayak", "rafting",
    "senderismo", "montaña", "cañon", "cañón", "barranca",
]
_KW_DESCANSO = [
    "balneario", "termal", "spa", "resort", "retiro", "hammam",
    "aguas termales", "hotel boutique",
]
_KW_EVENTOS = [
    "teatro", "auditorio", "foro", "festival", "expo", "feria",
    "centro cultural", "casa de cultura",
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
    return filas


# ── Entradas manuales para los lugares más famosos de Chiapas ─────────────────
# Se usan cuando OSM no los tiene o los tiene sin las etiquetas suficientes.
# foto_url: imágenes de Wikimedia Commons (dominio público).

LUGARES_FAMOSOS = [
    {
        "nombre": "Zona Arqueológica de Palenque",
        "tipo": "destino", "municipio": "Palenque", "categoria": "cultura",
        "costo_estimado": 90, "tiempo_horas": 3.5, "nivel_afluencia": 9500,
        "lat": 17.4838, "lng": -92.0458,
        "foto_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/54/Palenque_-_Temple_of_the_Inscriptions.jpg/800px-Palenque_-_Temple_of_the_Inscriptions.jpg",
    },
    {
        "nombre": "Cascada de Agua Azul",
        "tipo": "destino", "municipio": "Tumbalá", "categoria": "naturaleza",
        "costo_estimado": 60, "tiempo_horas": 3.0, "nivel_afluencia": 8200,
        "lat": 17.2589, "lng": -92.1131,
        "foto_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/15/Cascadas_de_Agua_Azul.jpg/800px-Cascadas_de_Agua_Azul.jpg",
    },
    {
        "nombre": "Cascada Misol-Ha",
        "tipo": "destino", "municipio": "Tumbalá", "categoria": "naturaleza",
        "costo_estimado": 50, "tiempo_horas": 1.5, "nivel_afluencia": 6800,
        "lat": 17.3577, "lng": -92.0998,
        "foto_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4e/Misol-Ha_waterfall.jpg/800px-Misol-Ha_waterfall.jpg",
    },
    {
        "nombre": "Cañón del Sumidero",
        "tipo": "destino", "municipio": "Chiapa de Corzo", "categoria": "naturaleza",
        "costo_estimado": 180, "tiempo_horas": 2.5, "nivel_afluencia": 9000,
        "lat": 16.8514, "lng": -93.0761,
        "foto_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/06/Canyon_del_Sumidero.jpg/800px-Canyon_del_Sumidero.jpg",
    },
    {
        "nombre": "Lagos de Montebello",
        "tipo": "destino", "municipio": "La Trinitaria", "categoria": "naturaleza",
        "costo_estimado": 50, "tiempo_horas": 4.0, "nivel_afluencia": 7500,
        "lat": 16.1119, "lng": -91.7219,
        "foto_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3c/Lagunas_de_Montebello_Chiapas.jpg/800px-Lagunas_de_Montebello_Chiapas.jpg",
    },
    {
        "nombre": "Cascada El Chiflón",
        "tipo": "destino", "municipio": "Tzimol", "categoria": "naturaleza",
        "costo_estimado": 80, "tiempo_horas": 3.0, "nivel_afluencia": 7000,
        "lat": 16.0894, "lng": -92.3006,
        "foto_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/ee/El_Chifl%C3%B3n.jpg/800px-El_Chifl%C3%B3n.jpg",
    },
    {
        "nombre": "Centro Histórico de San Cristóbal de las Casas",
        "tipo": "destino", "municipio": "San Cristobal de las Casas", "categoria": "cultura",
        "costo_estimado": 0, "tiempo_horas": 3.0, "nivel_afluencia": 9800,
        "lat": 16.7370, "lng": -92.6376,
        "foto_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/24/San_Cristobal_de_las_Casas_Cathedral.jpg/800px-San_Cristobal_de_las_Casas_Cathedral.jpg",
    },
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
        "nombre": "Mirador Cañón del Sumidero",
        "tipo": "destino", "municipio": "Tuxtla Gutierrez", "categoria": "fotografia",
        "costo_estimado": 30, "tiempo_horas": 1.0, "nivel_afluencia": 7200,
        "lat": 16.9034, "lng": -93.0489,
        "foto_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/06/Canyon_del_Sumidero.jpg/800px-Canyon_del_Sumidero.jpg",
    },
    {
        "nombre": "Zoológico Regional Miguel Álvarez del Toro (ZooMAT)",
        "tipo": "destino", "municipio": "Tuxtla Gutierrez", "categoria": "familiar",
        "costo_estimado": 50, "tiempo_horas": 3.0, "nivel_afluencia": 8500,
        "lat": 16.7191, "lng": -93.1295,
        "foto_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7e/Jaguar_at_ZooMAT.jpg/800px-Jaguar_at_ZooMAT.jpg",
    },
    {
        "nombre": "Balneario Agua Clara",
        "tipo": "destino", "municipio": "Salto de Agua", "categoria": "descanso",
        "costo_estimado": 80, "tiempo_horas": 3.5, "nivel_afluencia": 6000,
        "lat": 17.5714, "lng": -92.4019,
        "foto_url": "",
    },
    {
        "nombre": "Templo de Santo Domingo de Guzmán",
        "tipo": "destino", "municipio": "San Cristobal de las Casas", "categoria": "cultura",
        "costo_estimado": 0, "tiempo_horas": 1.0, "nivel_afluencia": 9200,
        "lat": 16.7397, "lng": -92.6383,
        "foto_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/90/Templo_de_Santo_Domingo%2C_San_Cristobal_de_las_Casas.jpg/800px-Templo_de_Santo_Domingo%2C_San_Cristobal_de_las_Casas.jpg",
    },
    {
        "nombre": "Parque Nacional Lagunas de Montebello",
        "tipo": "destino", "municipio": "La Trinitaria", "categoria": "aventura",
        "costo_estimado": 60, "tiempo_horas": 5.0, "nivel_afluencia": 7800,
        "lat": 16.0836, "lng": -91.7278,
        "foto_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3c/Lagunas_de_Montebello_Chiapas.jpg/800px-Lagunas_de_Montebello_Chiapas.jpg",
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
        "foto_url": "",
    },
]


def agregar_famosos(filas: list[dict]) -> list[dict]:
    nombres_existentes = {f["nombre"].lower() for f in filas}
    nuevos = 0
    for lugar in LUGARES_FAMOSOS:
        if lugar["nombre"].lower() not in nombres_existentes:
            filas.append({**lugar, "_wp": ""})
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

    print("4/4  Obteniendo fotos de Wikipedia...")
    todas = enriquecer_fotos(todas)
    con_foto = sum(1 for f in todas if f.get("foto_url"))
    print(f"     {con_foto} lugares con foto real de Wikipedia")

    escribir_csv(todas)

    # Resumen por categoría
    from collections import Counter
    cats = Counter(f["categoria"] for f in todas)
    munis = Counter(f["municipio"] for f in todas)
    print("\n── Distribución por categoría ──")
    for cat, n in sorted(cats.items(), key=lambda x: -x[1]):
        print(f"   {cat:15s}: {n}")
    print(f"\n── Municipios con más lugares ──")
    for muni, n in munis.most_common(10):
        print(f"   {muni:35s}: {n}")


if __name__ == "__main__":
    main()
