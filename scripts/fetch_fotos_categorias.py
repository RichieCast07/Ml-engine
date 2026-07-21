"""
Busca en Wikipedia (español) fotos representativas de cada categoria de interes
de ExploraChiapas y las guarda en data/fotos_categorias.json.

Ejecutar UNA SOLA VEZ para poblar el archivo de fotos:
    python scripts/fetch_fotos_categorias.py
"""

import json
import re
import urllib.request
import urllib.parse
from pathlib import Path

OUTPUT = Path("data/fotos_categorias.json")

# Articulo de Wikipedia (español) que mejor representa cada categoria
ARTICULOS = {
    "naturaleza":  "Cascadas de Agua Azul",
    "cultura":     "Zona arqueológica de Palenque",
    "gastronomia": "Gastronomía de Chiapas",
    "aventura":    "Cañón del Sumidero",
    "familiar":    "Zoológico Miguel Álvarez del Toro",
    "descanso":    "San Cristóbal de las Casas",
    "fotografia":  "Lagunas de Montebello",
    "eventos":     "Chiapa de Corzo",
    "restaurante": "Cocina chiapaneca",
}


def get_thumbnail(titulo: str) -> str | None:
    encoded = urllib.parse.quote(titulo.replace(" ", "_"))
    url = f"https://es.wikipedia.org/api/rest_v1/page/summary/{encoded}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ExploraChiapas/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())
            src = data.get("thumbnail", {}).get("source")
            if src:
                # Subir la resolución a 800px
                src = re.sub(r"/\d+px-", "/800px-", src)
            return src
    except Exception as exc:
        print(f"  [!] Error con '{titulo}': {exc}")
        return None


def main():
    resultado: dict[str, str | None] = {}

    for categoria, titulo in ARTICULOS.items():
        print(f"Buscando '{categoria}' -> '{titulo}' ...")
        url = get_thumbnail(titulo)
        resultado[categoria] = url
        if url:
            print(f"  OK  {url[:90]}")
        else:
            print(f"  SIN FOTO")

    OUTPUT.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    encontradas = sum(1 for v in resultado.values() if v)
    print(f"\nGuardado en {OUTPUT}")
    print(f"Fotos encontradas: {encontradas}/{len(resultado)}")


if __name__ == "__main__":
    main()
