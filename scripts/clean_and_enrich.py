"""
Post-procesamiento del dataset de destinos de Chiapas:
  1. Filtra categorias no turisticas (coladas por regex OSM)
  2. Enriquece con descripciones de Wikipedia ES
  3. Guarda dataset limpio en data/destinos_chiapas_clean.json

Uso:
  python scripts/clean_and_enrich.py
"""

import json
import time
import re
import sys
import urllib.request
import urllib.parse
from typing import Optional

INPUT_FILE  = "data/destinos_chiapas_full.json"
OUTPUT_FILE = "data/destinos_chiapas_clean.json"
WIKI_API    = "https://es.wikipedia.org/w/api.php"
WIKI_SLEEP  = 0.35

HEADERS = {"User-Agent": "ExploraChiapas-DataBot/1.0 (contacto@explorachiapas.mx)"}

# ── Categorias que SI son turisticas ──────────────────────
CATEGORIAS_VALIDAS = {
    "atractivo turistico", "museo", "hotel", "mirador", "zoologico",
    "parque tematico", "galeria de arte", "campamento", "hostal", "cabana",
    "area de picnic", "restaurante", "cafe", "bar", "mercado",
    "iglesia / templo", "iglesia historica", "monumento historico",
    "zona arqueologica", "castillo / fuerte", "monumento conmemorativo",
    "cascada", "manantial", "cueva / cenote", "playa / laguna",
    "montana / volcan", "aguas termales", "parque", "reserva natural",
    "jardin botanico", "artesania", "galeria / arte", "tienda de souvenirs",
    "area natural protegida", "punto de interes",
}

# ── Palabras clave en el nombre que garantizan lugar turistico ──
KEYWORDS_TURISTICOS = [
    "cascada", "waterfall", "cerro", "laguna", "lago", "parque", "reserva",
    "zona arqueologica", "museo", "mirador", "ruinas", "templo", "iglesia",
    "catedral", "santuario", "convento", "hacienda", "palacio", "ex-convento",
    "balneario", "cenote", "cueva", "gruta", "canon", "volcan", "selva",
    "manantial", "rio", "playa", "cascadas", "ecoturismo", "bioreserva",
    "jardin", "botanico", "mercado", "artesania", "malacon", "zocalo",
    "plaza", "monumento", "estatua", "fuente", "kiosko", "teatro",
]

def es_turistico(destino: dict) -> bool:
    cat = destino.get("categoria", "").lower()
    nombre = destino.get("nombre", "").lower()

    # Categorias claramente no turisticas
    if cat in ("car parts", "department store", "internet cafe", "supermarket",
               "convenience", "clothes", "shoes", "electronics", "hardware",
               "car repair", "fuel", "bank", "pharmacy", "hospital", "school",
               "kindergarten", "clinic", "dentist", "police", "fire_station",
               "post_office", "government", "office"):
        return False

    # Si la categoria es valida, siempre incluir
    if cat in CATEGORIAS_VALIDAS:
        return True

    # Si la categoria es desconocida, evaluar por palabras clave del nombre
    for kw in KEYWORDS_TURISTICOS:
        if kw in nombre:
            return True

    return False

# ── Wikipedia ──────────────────────────────────────────────
_cache: dict = {}

def wiki(title: str) -> Optional[str]:
    if title in _cache:
        return _cache[title]
    try:
        req = urllib.request.Request(
            WIKI_API + "?" + urllib.parse.urlencode({
                "action": "query", "prop": "extracts",
                "exintro": 1, "explaintext": 1, "redirects": 1,
                "titles": title, "format": "json",
            }),
            headers=HEADERS,
        )
        with urllib.request.urlopen(req, timeout=25) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print(f"    wiki WARN [{title[:40]}]: {e}", flush=True)
        _cache[title] = None
        return None
    finally:
        time.sleep(WIKI_SLEEP)

    for page in data.get("query", {}).get("pages", {}).values():
        if page.get("pageid", -1) != -1:
            text = re.sub(r"\s+", " ", page.get("extract", "")).strip()
            words = text.split()
            if len(words) > 250:
                text = " ".join(words[:250]) + "..."
            _cache[title] = text if len(text) > 60 else None
            return _cache[title]

    _cache[title] = None
    return None

def enriquecer(destino: dict) -> dict:
    if destino.get("descripcion"):
        return destino

    extra = destino.get("_osm_extra", {})
    wiki_tag = extra.get("wikipedia", "")
    if wiki_tag.startswith("es:"):
        desc = wiki(wiki_tag[3:])
        if desc:
            destino["descripcion"] = desc
            return destino

    desc = wiki(destino["nombre"])
    if desc:
        destino["descripcion"] = desc
    return destino

# ── Main ───────────────────────────────────────────────────
def main():
    print("=" * 55, flush=True)
    print("ExploraChiapas - Limpieza y enriquecimiento", flush=True)
    print("=" * 55, flush=True)

    print(f"\n[1/3] Cargando {INPUT_FILE}...", flush=True)
    with open(INPUT_FILE, encoding="utf-8") as f:
        raw = json.load(f)
    print(f"  Total cargado: {len(raw)}", flush=True)

    print("\n[2/3] Filtrando categorias no turisticas...", flush=True)
    filtrados = [d for d in raw if es_turistico(d)]
    removidos = len(raw) - len(filtrados)
    print(f"  Conservados: {len(filtrados)} | Removidos: {removidos}", flush=True)

    # Re-indexar
    for i, d in enumerate(filtrados, 1):
        d["id"] = i

    print(f"\n[3/3] Enriqueciendo con Wikipedia ({len(filtrados)} destinos)...", flush=True)
    sin_desc = [d for d in filtrados if not d.get("descripcion")]
    print(f"  Destinos sin descripcion: {len(sin_desc)}", flush=True)
    print(f"  Consultando Wikipedia para cada uno (puede tardar ~{len(sin_desc)//5} min)...", flush=True)

    enriquecidos = 0
    for i, d in enumerate(filtrados, 1):
        antes = bool(d.get("descripcion"))
        d = enriquecer(d)
        filtrados[i-1] = d
        if not antes and d.get("descripcion"):
            enriquecidos += 1
        if i % 100 == 0:
            con_desc = sum(1 for x in filtrados[:i] if x.get("descripcion"))
            print(f"  {i}/{len(filtrados)} procesados | con desc: {con_desc}", flush=True)

    print(f"  Nuevas descripciones obtenidas: {enriquecidos}", flush=True)

    print(f"\nGuardando en {OUTPUT_FILE}...", flush=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(filtrados, f, ensure_ascii=False, indent=2)

    total = len(filtrados)
    con_desc  = sum(1 for d in filtrados if d.get("descripcion"))
    con_fotos = sum(1 for d in filtrados if d.get("fotos"))
    con_mun   = sum(1 for d in filtrados if d.get("municipio"))
    con_hora  = sum(1 for d in filtrados if d.get("horario"))

    print(f"\nResumen final ({total} destinos):", flush=True)
    print(f"  Descripcion : {con_desc}/{total} ({100*con_desc//total}%)", flush=True)
    print(f"  Fotos       : {con_fotos}/{total} ({100*con_fotos//total}%)", flush=True)
    print(f"  Municipio   : {con_mun}/{total} ({100*con_mun//total}%)", flush=True)
    print(f"  Horario     : {con_hora}/{total} ({100*con_hora//total}%)", flush=True)
    print("\nDone.", flush=True)

if __name__ == "__main__":
    main()
