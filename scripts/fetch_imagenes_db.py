"""
Busca fotos reales de destinos turisticos en Wikipedia (español) y genera
un archivo SQL para actualizar la columna imagen_url de la tabla destino.

Solo lanza peticiones a Wikipedia para categorias turisticas (cascadas, zonas
arqueologicas, etc.). Para el resto usa la foto de categoria mas apropiada.

Uso: python scripts/fetch_imagenes_db.py
Genera: scripts/update_imagenes.sql

Requisito previo: ejecutar la migracion de la columna imagen_url:
  20260721000001-destino-imagen-up.sql
"""

import json
import re
import time
import urllib.request
import urllib.parse
from pathlib import Path

DATA_FILE         = Path("data/destinos_chiapas_clean.json")
FOTOS_CATEGORIAS  = Path("data/fotos_categorias.json")
OUTPUT_SQL        = Path("scripts/update_imagenes.sql")

PAUSA             = 0.25   # segundos entre peticiones a Wikipedia
MAX_BUSQUEDAS     = 400    # limite de peticiones a Wikipedia por corrida

# Categorias que valen la pena buscar en Wikipedia por nombre especifico
CATEGORIAS_BUSCAR = {
    "cascada", "zona arqueologica", "area natural protegida", "reserva natural",
    "parque", "parque nacional", "museo", "iglesia historica", "iglesia / templo",
    "monumento historico", "cueva / cenote", "playa / laguna", "montana / volcan",
    "mirador", "zoologico", "atractivo turistico", "jardin botanico",
    "aguas termales", "manantial", "castillo / fuerte", "galeria / arte",
    "galeria de arte",
}

# Mapeo de categoria OSM a clave en fotos_categorias.json
MAPA_CATEGORIA_A_INTERES = {
    "zona arqueologica":      "cultura",
    "museo":                  "cultura",
    "iglesia historica":      "cultura",
    "iglesia / templo":       "cultura",
    "monumento historico":    "cultura",
    "castillo / fuerte":      "cultura",
    "galeria / arte":         "cultura",
    "galeria de arte":        "cultura",
    "cascada":                "naturaleza",
    "reserva natural":        "naturaleza",
    "parque":                 "naturaleza",
    "parque nacional":        "naturaleza",
    "area natural protegida": "naturaleza",
    "playa / laguna":         "naturaleza",
    "jardin botanico":        "naturaleza",
    "manantial":              "naturaleza",
    "montana / volcan":       "aventura",
    "cueva / cenote":         "aventura",
    "mirador":                "fotografia",
    "aguas termales":         "descanso",
    "zoologico":              "familiar",
    "atractivo turistico":    "cultura",
    "restaurante":            "restaurante",
    "cafe":                   "restaurante",
    "bar":                    "restaurante",
    "hotel":                  "descanso",
    "hostal":                 "descanso",
    "cabana":                 "descanso",
    "campamento":             "aventura",
    "mercado":                "gastronomia",
    "artesania":              "cultura",
    "tienda de souvenirs":    "cultura",
    "parque tematico":        "familiar",
}


def get_thumbnail(titulo: str, municipio: str) -> str | None:
    """Busca thumbnail en Wikipedia ES primero por nombre+municipio, luego solo por nombre."""
    for query in [f"{titulo} {municipio}", titulo]:
        encoded = urllib.parse.quote(query.replace(" ", "_"))
        url = f"https://es.wikipedia.org/api/rest_v1/page/summary/{encoded}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ExploraChiapas/1.0"})
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = json.loads(resp.read())
                src = data.get("thumbnail", {}).get("source")
                if src:
                    src = re.sub(r"/\d+px-", "/800px-", src)
                    return src
        except Exception:
            pass
        time.sleep(PAUSA)
    return None


def esc_sql(value: str) -> str:
    """Escapa una cadena para usar dentro de comillas simples en MySQL."""
    return value.replace("\\", "\\\\").replace("'", "\\'")


def main():
    with open(DATA_FILE, encoding="utf-8") as f:
        destinos = json.load(f)

    with open(FOTOS_CATEGORIAS, encoding="utf-8") as f:
        fotos_cat = json.load(f)

    updates: list[str] = []
    busquedas_hechas = 0
    sin_foto = 0

    print(f"Procesando {len(destinos)} destinos...")

    for d in destinos:
        nombre    = (d.get("nombre") or "").strip()
        municipio = (d.get("municipio") or "").strip()
        categoria = (d.get("categoria") or "").lower().strip()

        if not nombre:
            continue

        url: str | None = None

        if categoria in CATEGORIAS_BUSCAR and busquedas_hechas < MAX_BUSQUEDAS:
            url = get_thumbnail(nombre, municipio)
            busquedas_hechas += 1
            if busquedas_hechas % 50 == 0:
                print(f"  {busquedas_hechas} busquedas en Wikipedia, {len(updates)} fotos encontradas...")

        if not url:
            interes = MAPA_CATEGORIA_A_INTERES.get(categoria)
            if interes:
                url = fotos_cat.get(interes)

        if url:
            nombre_esc = esc_sql(nombre)
            url_esc    = esc_sql(url)
            updates.append(
                f"UPDATE destino SET imagen_url = '{url_esc}' "
                f"WHERE LOWER(nombre) = LOWER('{nombre_esc}');"
            )
        else:
            sin_foto += 1

    lineas = [
        "-- Fotos de destinos de Chiapas desde Wikipedia",
        "-- Requiere que la migracion 20260721000001-destino-imagen-up.sql haya sido ejecutada",
        f"-- Total UPDATE: {len(updates)}  |  Sin foto: {sin_foto}",
        "",
    ] + updates + [""]

    OUTPUT_SQL.write_text("\n".join(lineas), encoding="utf-8")

    print(f"\nListo.")
    print(f"  Wikipedia consultada:  {busquedas_hechas} destinos")
    print(f"  Fotos encontradas:     {len(updates)}")
    print(f"  Sin foto:              {sin_foto}")
    print(f"  Archivo generado:      {OUTPUT_SQL}")


if __name__ == "__main__":
    main()
