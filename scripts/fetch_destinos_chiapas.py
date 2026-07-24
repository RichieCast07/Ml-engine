"""
Fetch destinos turisticos reales de Chiapas.
API: Overpass (OpenStreetMap) - gratuita, sin clave.
     Wikipedia ES              - gratuita, sin clave.

Uso:
  python scripts/fetch_destinos_chiapas.py          # solo OSM
  python scripts/fetch_destinos_chiapas.py --wiki   # + descripciones Wikipedia
"""

import json
import time
import re
import sys
import urllib.request
import urllib.parse
import argparse
from typing import Optional
from collections import Counter

# ── Configuracion ─────────────────────────────────────────
BBOX         = "14.53,-92.99,17.93,-90.37"   # Chiapas bounding box
OUTPUT_FILE  = "data/destinos_chiapas_full.json"
HTTP_TIMEOUT = 90
WIKI_SLEEP   = 0.4

OVERPASS_SERVERS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

WIKI_API = "https://es.wikipedia.org/w/api.php"

# ── Mapeo OSM tags -> categoria ────────────────────────────
CATEGORY_MAP = {
    ("tourism","attraction"):           "atractivo turistico",
    ("tourism","museum"):               "museo",
    ("tourism","hotel"):                "hotel",
    ("tourism","viewpoint"):            "mirador",
    ("tourism","zoo"):                  "zoologico",
    ("tourism","theme_park"):           "parque tematico",
    ("tourism","gallery"):              "galeria de arte",
    ("tourism","camp_site"):            "campamento",
    ("tourism","guest_house"):          "hostal",
    ("tourism","chalet"):               "cabana",
    ("tourism","picnic_site"):          "area de picnic",
    ("amenity","restaurant"):           "restaurante",
    ("amenity","cafe"):                 "cafe",
    ("amenity","bar"):                  "bar",
    ("amenity","marketplace"):          "mercado",
    ("amenity","place_of_worship"):     "iglesia / templo",
    ("historic","monument"):            "monumento historico",
    ("historic","ruins"):               "zona arqueologica",
    ("historic","archaeological_site"): "zona arqueologica",
    ("historic","castle"):              "castillo / fuerte",
    ("historic","fort"):                "castillo / fuerte",
    ("historic","church"):              "iglesia historica",
    ("historic","memorial"):            "monumento conmemorativo",
    ("natural","waterfall"):            "cascada",
    ("natural","spring"):               "manantial",
    ("natural","cave_entrance"):        "cueva / cenote",
    ("natural","beach"):                "playa / laguna",
    ("natural","peak"):                 "montana / volcan",
    ("natural","hot_spring"):           "aguas termales",
    ("leisure","park"):                 "parque",
    ("leisure","nature_reserve"):       "reserva natural",
    ("leisure","garden"):               "jardin botanico",
    ("craft","pottery"):                "artesania",
    ("craft","jeweller"):               "artesania",
    ("craft","weaver"):                 "artesania",
    ("shop","craft"):                   "artesania",
    ("shop","art"):                     "galeria / arte",
    ("shop","souvenir"):                "tienda de souvenirs",
}

# ── HTTP helpers ───────────────────────────────────────────
HEADERS = {
    "User-Agent": "ExploraChiapas-DataBot/1.0 (contacto@explorachiapas.mx)"
}

def post(url: str, body: str, timeout: int = HTTP_TIMEOUT) -> Optional[dict]:
    try:
        req = urllib.request.Request(
            url,
            data=("data=" + urllib.parse.quote(body)).encode("utf-8"),
            headers={**HEADERS, "Content-Type": "application/x-www-form-urlencoded"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print(f"    WARN: {e}", flush=True)
        return None

def get(url: str, params: dict, timeout: int = 30) -> Optional[dict]:
    full = url + "?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(full, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print(f"    WARN wiki: {e}", flush=True)
        return None

def overpass(query: str, label: str) -> list:
    for server in OVERPASS_SERVERS:
        host = server.split("/")[2]
        print(f"  [{label}] {host}...", flush=True)
        result = post(server, query)
        if result and "elements" in result:
            n = len(result["elements"])
            print(f"  [{label}] OK - {n} elementos", flush=True)
            return result["elements"]
        print(f"  [{label}] fallo, probando siguiente...", flush=True)
        time.sleep(2)
    print(f"  [{label}] TODOS LOS SERVIDORES FALLARON", flush=True)
    return []

# ── Queries Overpass (3 bloques para evitar timeout) ───────
def fetch_all() -> list:
    blocks = [
        ("turismo+amenidades", f"""
[out:json][timeout:90];
(
  node["tourism"~"attraction|museum|hotel|viewpoint|zoo|theme_park|gallery|camp_site|guest_house|chalet"]({BBOX});
  way["tourism"~"attraction|museum|hotel|viewpoint|zoo|theme_park|gallery|camp_site|guest_house|chalet"]({BBOX});
  node["amenity"~"restaurant|cafe|bar|marketplace"]({BBOX});
  way["amenity"~"restaurant|cafe|bar|marketplace"]({BBOX});
);
out center tags;"""),

        ("historico+natural", f"""
[out:json][timeout:90];
(
  node["historic"~"monument|ruins|archaeological_site|castle|fort|church|memorial"]({BBOX});
  way["historic"~"monument|ruins|archaeological_site|castle|fort|church|memorial"]({BBOX});
  node["natural"~"waterfall|spring|cave_entrance|beach|peak|hot_spring"]({BBOX});
  way["natural"~"waterfall|spring|cave_entrance|beach|peak|hot_spring"]({BBOX});
);
out center tags;"""),

        ("leisure+artesania+templos", f"""
[out:json][timeout:90];
(
  node["leisure"~"park|nature_reserve|garden"]({BBOX});
  way["leisure"~"park|nature_reserve|garden"]({BBOX});
  node["craft"~"pottery|jeweller|weaver"]({BBOX});
  node["shop"~"craft|art|souvenir"]({BBOX});
  node["amenity"="place_of_worship"]({BBOX});
  way["amenity"="place_of_worship"]({BBOX});
);
out center tags;"""),
    ]

    all_elements = []
    seen = set()
    for label, query in blocks:
        elements = overpass(query.strip(), label)
        added = 0
        for el in elements:
            key = (el["type"], el["id"])
            if key not in seen:
                seen.add(key)
                all_elements.append(el)
                added += 1
        print(f"  Nuevos unicos: {added} | Total: {len(all_elements)}", flush=True)
        time.sleep(5)

    return all_elements

# ── Wikipedia ──────────────────────────────────────────────
_wiki_cache: dict = {}

def wiki_extract(title: str) -> Optional[str]:
    if title in _wiki_cache:
        return _wiki_cache[title]
    data = get(WIKI_API, {
        "action": "query", "prop": "extracts",
        "exintro": 1, "explaintext": 1, "redirects": 1,
        "titles": title, "format": "json",
    })
    time.sleep(WIKI_SLEEP)
    if not data:
        _wiki_cache[title] = None
        return None
    for page in data.get("query", {}).get("pages", {}).values():
        if page.get("pageid", -1) != -1:
            text = re.sub(r"\s+", " ", page.get("extract", "")).strip()
            words = text.split()
            if len(words) > 250:
                text = " ".join(words[:250]) + "..."
            _wiki_cache[title] = text or None
            return _wiki_cache[title]
    _wiki_cache[title] = None
    return None

def get_descripcion(tags: dict, nombre: str, use_wiki: bool) -> Optional[str]:
    for key in ("description", "description:es"):
        v = tags.get(key, "")
        if v and len(v) > 30:
            return v.strip()
    if not use_wiki:
        return None
    wiki_tag = tags.get("wikipedia", "")
    if wiki_tag.startswith("es:"):
        d = wiki_extract(wiki_tag[3:])
        if d:
            return d
    return wiki_extract(nombre)

# ── Transformar elemento OSM ───────────────────────────────
def coords(el: dict) -> Optional[dict]:
    if el["type"] == "node":
        lat, lon = el.get("lat"), el.get("lon")
        if lat and lon:
            return {"lat": round(lat, 6), "lng": round(lon, 6)}
    c = el.get("center", {})
    if c:
        return {"lat": round(c["lat"], 6), "lng": round(c["lon"], 6)}
    return None

def categoria(tags: dict) -> str:
    for key in ("tourism","amenity","historic","natural","leisure","craft","shop"):
        val = tags.get(key)
        if val:
            cat = CATEGORY_MAP.get((key, val))
            return cat if cat else val.replace("_", " ")
    return "punto de interes"

def municipio(tags: dict) -> Optional[str]:
    for key in ("addr:city","addr:municipality","is_in:municipality","is_in:city"):
        v = tags.get(key)
        if v:
            return v
    return None

def horario(tags: dict) -> Optional[str]:
    oh = tags.get("opening_hours")
    if not oh:
        return None
    for en, es in [("Mo","Lun"),("Tu","Mar"),("We","Mie"),("Th","Jue"),
                   ("Fr","Vie"),("Sa","Sab"),("Su","Dom")]:
        oh = oh.replace(en, es)
    return oh

def fotos(tags: dict) -> list:
    result = []
    for k in ("image","image:0","image:1","image:2"):
        u = tags.get(k, "")
        if u.startswith("http"):
            result.append(u)
    commons = tags.get("wikimedia_commons", "")
    if commons.startswith("File:"):
        fname = urllib.parse.quote(commons[5:].replace(" ", "_"))
        result.append(f"https://commons.wikimedia.org/wiki/Special:FilePath/{fname}?width=800")
    return result

def transform(el: dict, idx: int, use_wiki: bool) -> Optional[dict]:
    tags = el.get("tags", {})
    nombre = (tags.get("name") or tags.get("name:es", "")).strip()
    if len(nombre) < 3:
        return None

    c = coords(el)
    if not c:
        return None

    estado = tags.get("addr:state", "") or tags.get("is_in:state", "")
    if estado and "chiapas" not in estado.lower():
        return None

    osm_type, osm_id = el["type"], el["id"]
    return {
        "id":                    idx,
        "nombre":                nombre,
        "categoria":             categoria(tags),
        "municipio":             municipio(tags),
        "direccion":             tags.get("addr:street"),
        "coordenadas":           c,
        "descripcion":           get_descripcion(tags, nombre, use_wiki),
        "fotos":                 fotos(tags),
        "calificacion_promedio": None,
        "resenas":               [],
        "horario":               horario(tags),
        "telefono":              tags.get("phone") or tags.get("contact:phone"),
        "fuente": f"OpenStreetMap {osm_type}/{osm_id} — https://www.openstreetmap.org/{osm_type}/{osm_id}",
        "_osm_extra": {k: v for k, v in tags.items() if k in (
            "website","contact:website","fee","wheelchair",
            "wikipedia","wikidata","wikimedia_commons",
            "tourism","amenity","historic","natural","leisure",
        )},
    }

# ── Main ───────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--wiki", action="store_true",
                        help="Enriquecer con Wikipedia (mas lento)")
    args = parser.parse_args()

    print("=" * 55, flush=True)
    print("ExploraChiapas - Destinos reales de Chiapas (OSM)", flush=True)
    print(f"Wikipedia: {'SI' if args.wiki else 'NO'}", flush=True)
    print("=" * 55, flush=True)

    print("\n[1/3] Descargando de OpenStreetMap...", flush=True)
    elements = fetch_all()
    if not elements:
        print("ERROR: Sin datos. Verifica tu conexion.", flush=True)
        sys.exit(1)

    print(f"\n[2/3] Transformando {len(elements)} elementos...", flush=True)
    destinos = []
    skipped  = 0
    for i, el in enumerate(elements, 1):
        d = transform(el, len(destinos) + 1, args.wiki)
        if d:
            destinos.append(d)
        else:
            skipped += 1
        if i % 300 == 0:
            print(f"  {i}/{len(elements)} | validos: {len(destinos)}", flush=True)

    print(f"  Validos: {len(destinos)} | Descartados: {skipped}", flush=True)

    print(f"\n[3/3] Guardando en {OUTPUT_FILE}...", flush=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(destinos, f, ensure_ascii=False, indent=2)
    print("  Guardado.", flush=True)

    # Estadisticas
    total = len(destinos)
    if total == 0:
        print("No se generaron destinos.", flush=True)
        return

    cats = Counter(d["categoria"] for d in destinos)
    print("\n  Por categoria (top 20):", flush=True)
    for cat, n in cats.most_common(20):
        bar = "#" * min(n // 3, 40)
        print(f"    {n:4d}  {cat:<32} {bar}", flush=True)

    con_desc  = sum(1 for d in destinos if d["descripcion"])
    con_fotos = sum(1 for d in destinos if d["fotos"])
    con_mun   = sum(1 for d in destinos if d["municipio"])
    con_hora  = sum(1 for d in destinos if d["horario"])
    print(f"\n  Completitud ({total} destinos):", flush=True)
    print(f"    Descripcion : {con_desc}/{total} ({100*con_desc//total}%)", flush=True)
    print(f"    Fotos       : {con_fotos}/{total} ({100*con_fotos//total}%)", flush=True)
    print(f"    Municipio   : {con_mun}/{total} ({100*con_mun//total}%)", flush=True)
    print(f"    Horario     : {con_hora}/{total} ({100*con_hora//total}%)", flush=True)

    print("\nDone.", flush=True)

if __name__ == "__main__":
    main()
