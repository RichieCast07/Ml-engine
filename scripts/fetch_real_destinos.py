"""
Descarga lugares turísticos reales de Chiapas desde OpenStreetMap (Overpass API),
asigna municipio con Nominatim y obtiene fotos reales con Google Places Photos API.

Uso básico (sin fotos):
  python scripts/fetch_real_destinos.py

Con fotos de Google Places (recomendado):
  python scripts/fetch_real_destinos.py --google-key TU_API_KEY

La API key de Google Places es gratis los primeros $200/mes (~10,000 búsquedas).
Activarla en: https://console.cloud.google.com → APIs → Places API (New)

El resultado se guarda en data/destinos_reales.csv y data/municipio_coords_nuevo.json.
Revisar antes de reemplazar los archivos originales.
"""

import argparse
import csv
import json
import time
from pathlib import Path

import requests

# ── Configuración ────────────────────────────────────────────────────────────

OVERPASS_SERVERS = [
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
OVERPASS_URL   = OVERPASS_SERVERS[0]  # se intenta en orden
NOMINATIM_URL  = "https://nominatim.openstreetmap.org/reverse"
PLACES_SEARCH  = "https://places.googleapis.com/v1/places:searchText"
PLACES_PHOTO   = "https://places.googleapis.com/v1/{name}/media"

OUT_CSV        = Path("data/destinos_reales.csv")
OUT_COORDS     = Path("data/municipio_coords_nuevo.json")

# ── Mapeo OSM → categoría ExploraChiapas ────────────────────────────────────

TAG_CATEGORIA = {
    "attraction":          "cultura",
    "viewpoint":           "fotografia",
    "museum":              "cultura",
    "gallery":             "cultura",
    "theme_park":          "familiar",
    "zoo":                 "familiar",
    "aquarium":            "familiar",
    "picnic_site":         "familiar",
    "camp_site":           "aventura",
    "waterfall":           "naturaleza",
    "cave_entrance":       "naturaleza",
    "peak":                "aventura",
    "spring":              "naturaleza",
    "beach":               "descanso",
    "hot_spring":          "descanso",
    "archaeological_site": "cultura",
    "ruins":               "cultura",
    "monument":            "cultura",
    "fort":                "cultura",
    "church":              "cultura",
    "cathedral":           "cultura",
    "restaurant":          None,   # tipo = restaurante
    "cafe":                None,
    "fast_food":           None,
    "park":                "familiar",
    "nature_reserve":      "naturaleza",
    "garden":              "descanso",
    "sports_centre":       "aventura",
}

# (costo_estimado MXN, tiempo_horas, nivel_afluencia 1-3)
TAG_COSTO_TIEMPO = {
    "waterfall":           (150, 3.0, 1),
    "cave_entrance":       (200, 2.5, 1),
    "peak":                (0,   5.0, 1),
    "spring":              (80,  2.0, 1),
    "hot_spring":          (120, 2.0, 1),
    "nature_reserve":      (100, 4.0, 1),
    "camp_site":           (300, 8.0, 1),
    "viewpoint":           (50,  1.5, 2),
    "ruins":               (100, 2.0, 2),
    "gallery":             (60,  1.5, 2),
    "park":                (30,  2.0, 2),
    "garden":              (30,  1.5, 2),
    "fort":                (80,  2.0, 2),
    "monument":            (0,   0.5, 2),
    "beach":               (0,   4.0, 2),
    "picnic_site":         (0,   2.0, 2),
    "sports_centre":       (80,  2.0, 2),
    "church":              (0,   1.0, 2),
    "cathedral":           (0,   1.0, 2),
    "museum":              (80,  2.0, 3),
    "archaeological_site": (120, 3.0, 3),
    "attraction":          (120, 2.5, 3),
    "theme_park":          (250, 4.0, 3),
    "zoo":                 (150, 3.0, 3),
    "aquarium":            (120, 2.0, 3),
    "restaurant":          (280, 1.5, 2),
    "cafe":                (150, 1.0, 2),
    "fast_food":           (80,  0.5, 3),
}
DEFAULT_COSTO_TIEMPO = (100, 2.0, 2)

# ── Query Overpass ───────────────────────────────────────────────────────────

# Relación OSM para el estado de Chiapas
# Bounding box del estado de Chiapas (sur, oeste, norte, este)
# Formato Overpass: (min_lat, min_lon, max_lat, max_lon)
CHIAPAS_BB = "(14.53,-94.24,17.88,-90.37)"

OVERPASS_QUERY = f"""
[out:json][timeout:180];
(
  node["tourism"="attraction"]["name"]{CHIAPAS_BB};
  node["tourism"="viewpoint"]["name"]{CHIAPAS_BB};
  node["tourism"="museum"]["name"]{CHIAPAS_BB};
  node["tourism"="gallery"]["name"]{CHIAPAS_BB};
  node["tourism"="theme_park"]["name"]{CHIAPAS_BB};
  node["tourism"="zoo"]["name"]{CHIAPAS_BB};
  node["tourism"="picnic_site"]["name"]{CHIAPAS_BB};
  node["tourism"="camp_site"]["name"]{CHIAPAS_BB};
  node["natural"="waterfall"]["name"]{CHIAPAS_BB};
  node["natural"="cave_entrance"]["name"]{CHIAPAS_BB};
  node["natural"="peak"]["name"]{CHIAPAS_BB};
  node["natural"="spring"]["name"]{CHIAPAS_BB};
  node["natural"="hot_spring"]["name"]{CHIAPAS_BB};
  node["natural"="beach"]["name"]{CHIAPAS_BB};
  node["historic"="archaeological_site"]["name"]{CHIAPAS_BB};
  node["historic"="ruins"]["name"]{CHIAPAS_BB};
  node["historic"="monument"]["name"]{CHIAPAS_BB};
  node["amenity"="restaurant"]["name"]{CHIAPAS_BB};
  node["amenity"="cafe"]["name"]{CHIAPAS_BB};
  node["leisure"="park"]["name"]{CHIAPAS_BB};
  node["leisure"="nature_reserve"]["name"]{CHIAPAS_BB};
  node["leisure"="garden"]["name"]{CHIAPAS_BB};
  way["tourism"="attraction"]["name"]{CHIAPAS_BB};
  way["tourism"="viewpoint"]["name"]{CHIAPAS_BB};
  way["tourism"="museum"]["name"]{CHIAPAS_BB};
  way["natural"="waterfall"]["name"]{CHIAPAS_BB};
  way["natural"="cave_entrance"]["name"]{CHIAPAS_BB};
  way["historic"="archaeological_site"]["name"]{CHIAPAS_BB};
  way["historic"="ruins"]["name"]{CHIAPAS_BB};
  way["leisure"="park"]["name"]{CHIAPAS_BB};
  way["leisure"="nature_reserve"]["name"]{CHIAPAS_BB};
);
out center tags;
"""

# ── Helpers ──────────────────────────────────────────────────────────────────

def _tag_principal(tags: dict) -> tuple[str, str]:
    for key in ("natural", "historic", "tourism", "leisure", "amenity", "building"):
        if key in tags:
            return tags[key], key
    return "", ""


def _municipio_nominatim(lat: float, lon: float) -> tuple[str, float, float]:
    """Devuelve (municipio, lat_centro, lon_centro) usando Nominatim."""
    try:
        r = requests.get(
            NOMINATIM_URL,
            params={"lat": lat, "lon": lon, "format": "json",
                    "addressdetails": 1, "zoom": 8},
            headers={"User-Agent": "ExploraChiapas-ML/1.0 (proyecto educativo)"},
            timeout=12,
        )
        r.raise_for_status()
        data = r.json()
        addr = data.get("address", {})
        for campo in ("municipality", "city", "town", "village", "county", "suburb"):
            if addr.get(campo):
                return addr[campo], lat, lon
        return "Chiapas", lat, lon
    except Exception:
        return "Chiapas", lat, lon


def _foto_google_places(nombre: str, municipio: str, api_key: str) -> str | None:
    """Busca el lugar en Google Places (New API) y devuelve URL de foto."""
    try:
        query = f"{nombre} {municipio} Chiapas Mexico"
        resp = requests.post(
            PLACES_SEARCH,
            json={"textQuery": query, "maxResultCount": 1,
                  "languageCode": "es"},
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": api_key,
                "X-Goog-FieldMask": "places.id,places.photos",
            },
            timeout=12,
        )
        resp.raise_for_status()
        places = resp.json().get("places", [])
        if not places:
            return None

        fotos = places[0].get("photos", [])
        if not fotos:
            return None

        foto_name = fotos[0]["name"]  # "places/{id}/photos/{ref}"
        url = (
            f"https://places.googleapis.com/v1/{foto_name}/media"
            f"?maxHeightPx=800&maxWidthPx=1200&key={api_key}"
        )
        return url
    except Exception as e:
        return None


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--google-key", metavar="KEY",
                        help="API key de Google Places (New) para obtener fotos reales")
    args = parser.parse_args()

    # 1. Descargar datos de OpenStreetMap
    print("=" * 60)
    print("PASO 1: Descargando lugares desde OpenStreetMap...")
    print("(puede tardar 30-60 segundos)")

    headers = {
        "User-Agent": "ExploraChiapas-ML/1.0 (proyecto educativo universitario)",
        "Accept": "application/json",
    }
    elementos = []
    for servidor in OVERPASS_SERVERS:
        try:
            print(f"  Intentando {servidor}...")
            r = requests.post(servidor, data={"data": OVERPASS_QUERY},
                              headers=headers, timeout=200)
            r.raise_for_status()
            elementos = r.json().get("elements", [])
            print(f"  OK — {len(elementos)} elementos descargados")
            break
        except Exception as e:
            print(f"  Fallo ({e}), probando siguiente servidor...")
            time.sleep(3)
    if not elementos:
        print("ERROR: No se pudo conectar a ningún servidor Overpass.")
        return
    print(f"  {len(elementos)} elementos OSM descargados")

    # 2. Filtrar y estructurar
    filas: list[dict] = []
    nombres_vistos: set[str] = set()
    dest_id = 1

    for el in elementos:
        tags = el.get("tags", {})
        nombre = tags.get("name", "").strip()
        if not nombre or nombre in nombres_vistos:
            continue
        nombres_vistos.add(nombre)

        if el["type"] == "node":
            lat, lon = el.get("lat"), el.get("lon")
        else:
            centro = el.get("center", {})
            lat, lon = centro.get("lat"), centro.get("lon")
        if lat is None or lon is None:
            continue

        tag_val, _ = _tag_principal(tags)
        if not tag_val or tag_val not in TAG_CATEGORIA and tag_val not in TAG_COSTO_TIEMPO:
            continue

        categoria = TAG_CATEGORIA.get(tag_val)
        tipo = "restaurante" if categoria is None else "destino"
        costo, tiempo, afluencia = TAG_COSTO_TIEMPO.get(tag_val, DEFAULT_COSTO_TIEMPO)

        filas.append({
            "id":              dest_id,
            "nombre":          nombre,
            "tipo":            tipo,
            "categoria":       categoria or "",
            "municipio":       "",       # se rellena en paso 3
            "_lat":            lat,
            "_lon":            lon,
            "costo_estimado":  costo,
            "tiempo_horas":    tiempo,
            "nivel_afluencia": afluencia,
            "foto_url":        "",
        })
        dest_id += 1

    print(f"  {len(filas)} lugares válidos con nombre")

    # 3. Asignar municipio con Nominatim (1 req/seg por política)
    print()
    print("PASO 2: Asignando municipios con Nominatim...")
    print(f"  (tardará ~{len(filas) * 1.2 / 60:.0f} minutos — 1 solicitud/segundo)")

    coords_municipios: dict[str, dict] = {}
    municipio_puntos: dict[str, list[tuple[float, float]]] = {}

    for i, fila in enumerate(filas, 1):
        if i % 25 == 0 or i == 1:
            print(f"  {i}/{len(filas)} municipios asignados...")
        muni, lat, lon = _municipio_nominatim(fila["_lat"], fila["_lon"])
        fila["municipio"] = muni
        municipio_puntos.setdefault(muni, []).append((lat, lon))
        time.sleep(1.1)

    # Calcular centroide por municipio
    for muni, puntos in municipio_puntos.items():
        coords_municipios[muni] = {
            "lat": sum(p[0] for p in puntos) / len(puntos),
            "lng": sum(p[1] for p in puntos) / len(puntos),
        }

    # 4. Obtener fotos con Google Places (si se proporcionó key)
    if args.google_key:
        print()
        print("PASO 3: Obteniendo fotos con Google Places API...")
        print(f"  (~{len(filas)} solicitudes, puede tardar varios minutos)")
        for i, fila in enumerate(filas, 1):
            if i % 25 == 0 or i == 1:
                print(f"  {i}/{len(filas)} fotos procesadas...")
            foto = _foto_google_places(fila["nombre"], fila["municipio"], args.google_key)
            if foto:
                fila["foto_url"] = foto
            time.sleep(0.3)
        con_foto = sum(1 for f in filas if f["foto_url"])
        print(f"  {con_foto}/{len(filas)} lugares con foto encontrada")
    else:
        print()
        print("PASO 3: Omitiendo fotos (usa --google-key para obtenerlas)")

    # 5. Escribir CSV
    print()
    print("PASO 4: Guardando archivos...")
    columnas = ["id", "nombre", "tipo", "categoria", "municipio",
                "costo_estimado", "tiempo_horas", "nivel_afluencia", "foto_url"]

    OUT_CSV.parent.mkdir(exist_ok=True)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columnas, extrasaction="ignore")
        w.writeheader()
        w.writerows(filas)

    OUT_COORDS.write_text(
        json.dumps(coords_municipios, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Estadísticas
    total      = len(filas)
    destinos   = sum(1 for r in filas if r["tipo"] == "destino")
    restaurantes = total - destinos
    municipios = len(coords_municipios)
    con_foto   = sum(1 for r in filas if r["foto_url"])

    print()
    print("=" * 60)
    print(f"LISTO")
    print(f"  Total lugares:      {total}")
    print(f"  Destinos:           {destinos}")
    print(f"  Restaurantes:       {restaurantes}")
    print(f"  Municipios:         {municipios}")
    print(f"  Con foto:           {con_foto}")
    print()
    print(f"Archivos generados:")
    print(f"  {OUT_CSV}")
    print(f"  {OUT_COORDS}")
    print()
    print("Para usar los datos reales en el motor ML:")
    print("  cp data/destinos_reales.csv data/destinos.csv")
    print("  cp data/municipio_coords_nuevo.json data/municipio_coords.json")
    print("  pm2 restart ml-engine")


if __name__ == "__main__":
    main()
