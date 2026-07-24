"""
Genera seed SQL para poblar la BD de ExploraChiapas desde el dataset OSM.

Lee:  data/destinos_chiapas_clean.json  (si existe)
      data/destinos_chiapas_full.json   (fallback)
Crea: scripts/seed_destinos.sql

Tablas que popula (en orden correcto de FK):
  1. origen_ubicacion  — agrega fila "osm" si no existe
  2. categoria         — una fila por categoria unica
  3. ubicacion         — una fila por destino
  4. destino           — una fila por destino
  5. destino_metrica   — una fila por destino (metricas en cero)
"""

import json
import uuid
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── Configuracion ──────────────────────────────────────────
CLEAN_FILE = Path("data/destinos_chiapas_clean.json")
FULL_FILE  = Path("data/destinos_chiapas_full.json")
OUTPUT_SQL = Path("scripts/seed_destinos.sql")

# Limite opcional para no generar un archivo enorme de golpe
# Cambia a None para incluir todos los destinos
MAX_DESTINOS = None

# ── Helpers ────────────────────────────────────────────────
def uid() -> str:
    return str(uuid.uuid4())

def esc(value) -> str:
    """Escapa un valor para SQL: None → NULL, string → 'valor con escapes'."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    # Escapar comillas simples y barras
    s = str(value).replace("\\", "\\\\").replace("'", "\\'")
    return f"'{s}'"

def now_sql() -> str:
    return datetime.now(timezone.utc).strftime("'%Y-%m-%d %H:%M:%S'")

# ── Main ───────────────────────────────────────────────────
def main():
    # Elegir archivo de entrada
    if CLEAN_FILE.exists():
        input_file = CLEAN_FILE
        print(f"Usando archivo limpio: {CLEAN_FILE}", flush=True)
    elif FULL_FILE.exists():
        input_file = FULL_FILE
        print(f"Archivo limpio no existe aun, usando: {FULL_FILE}", flush=True)
    else:
        print("ERROR: No se encontro ningun archivo de destinos.", flush=True)
        sys.exit(1)

    with open(input_file, encoding="utf-8") as f:
        destinos = json.load(f)

    if MAX_DESTINOS:
        destinos = destinos[:MAX_DESTINOS]

    print(f"Generando SQL para {len(destinos)} destinos...", flush=True)

    # ── Colectar categorias unicas ─────────────────────────
    categorias_unicas = sorted(set(
        d["categoria"] for d in destinos if d.get("categoria")
    ))
    cat_map: dict[str, str] = {cat: uid() for cat in categorias_unicas}

    # ID fijo para origen OSM (para referencia cruzada consistente)
    origen_osm_id = uid()
    now = now_sql()

    lines = []

    # ── Cabecera ───────────────────────────────────────────
    lines.append("-- ============================================================")
    lines.append(f"-- Seed de destinos de Chiapas — generado {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"-- Fuente: OpenStreetMap via Overpass API")
    lines.append(f"-- Total destinos: {len(destinos)}")
    lines.append(f"-- Total categorias: {len(cat_map)}")
    lines.append("-- ============================================================")
    lines.append("")
    lines.append("SET FOREIGN_KEY_CHECKS = 0;")
    lines.append("SET NAMES utf8mb4;")
    lines.append("")

    # ── 1. origen_ubicacion (OSM) ──────────────────────────
    lines.append("-- 1. Origen de ubicaciones")
    lines.append(f"INSERT IGNORE INTO `origen_ubicacion` (`id`, `nombre`) VALUES")
    lines.append(f"  ({esc(origen_osm_id)}, 'osm');")
    lines.append("")

    # ── 2. categorias ─────────────────────────────────────
    lines.append("-- 2. Categorias")
    lines.append("INSERT IGNORE INTO `categoria` (`id`, `nombre`, `icono`) VALUES")
    cat_rows = []
    for nombre, cat_id in cat_map.items():
        icono = _icono_categoria(nombre)
        cat_rows.append(f"  ({esc(cat_id)}, {esc(nombre)}, {esc(icono)})")
    lines.append(",\n".join(cat_rows) + ";")
    lines.append("")

    # ── 3+4+5. ubicacion + destino + destino_metrica ───────
    lines.append("-- 3. Ubicaciones")
    ubic_rows = []
    dest_rows = []
    metrica_rows = []

    for d in destinos:
        coords    = d.get("coordenadas") or {}
        lat       = coords.get("lat")
        lng       = coords.get("lng")
        if lat is None or lng is None:
            continue

        ubic_id   = uid()
        dest_id   = uid()
        cat_id    = cat_map.get(d.get("categoria", ""), list(cat_map.values())[0])
        municipio = d.get("municipio")
        direccion = d.get("direccion")
        nombre    = d.get("nombre", "")[:150]   # max varchar(150)
        desc      = d.get("descripcion")
        # Extraer OSM place_id del campo fuente: "OpenStreetMap node/12345 — ..."
        fuente    = d.get("fuente", "")
        osm_pid   = fuente.split(" — ")[0].replace("OpenStreetMap ", "") if fuente else None

        ubic_rows.append(
            f"  ({esc(ubic_id)}, {esc(lat)}, {esc(lng)}, {esc(direccion)}, "
            f"{esc(municipio)}, 'Chiapas', {esc(origen_osm_id)}, 'osm', "
            f"{esc(osm_pid)}, NULL, NULL, {now})"
        )
        dest_rows.append(
            f"  ({esc(dest_id)}, {esc(nombre)}, {esc(desc)}, {esc(cat_id)}, "
            f"{esc(ubic_id)}, 1, 0, {now})"
        )
        metrica_rows.append(
            f"  ({esc(dest_id)}, 0.00, 0, 0, 0, {now})"
        )

    # Insertar en lotes de 500 para no hacer un INSERT kilométrico
    BATCH = 500

    lines.append("INSERT INTO `ubicacion`")
    lines.append("  (`id`,`latitud`,`longitud`,`direccion`,`municipio`,`estado`,")
    lines.append("   `origen_id`,`proveedor_mapa`,`proveedor_place_id`,")
    lines.append("   `creado_por_usuario_id`,`estado_revision_id`,`fecha_creacion`)")
    lines.append("VALUES")
    for i in range(0, len(ubic_rows), BATCH):
        batch = ubic_rows[i:i+BATCH]
        if i + BATCH >= len(ubic_rows):
            lines.append(",\n".join(batch) + ";")
        else:
            lines.append(",\n".join(batch) + ";")
            lines.append("")
            lines.append("INSERT INTO `ubicacion`")
            lines.append("  (`id`,`latitud`,`longitud`,`direccion`,`municipio`,`estado`,")
            lines.append("   `origen_id`,`proveedor_mapa`,`proveedor_place_id`,")
            lines.append("   `creado_por_usuario_id`,`estado_revision_id`,`fecha_creacion`)")
            lines.append("VALUES")
    lines.append("")

    lines.append("-- 4. Destinos")
    lines.append("INSERT INTO `destino`")
    lines.append("  (`id`,`nombre`,`descripcion`,`categoria_id`,`ubicacion_id`,")
    lines.append("   `activo`,`es_sostenible`,`fecha_creacion`)")
    lines.append("VALUES")
    for i in range(0, len(dest_rows), BATCH):
        batch = dest_rows[i:i+BATCH]
        if i + BATCH >= len(dest_rows):
            lines.append(",\n".join(batch) + ";")
        else:
            lines.append(",\n".join(batch) + ";")
            lines.append("")
            lines.append("INSERT INTO `destino`")
            lines.append("  (`id`,`nombre`,`descripcion`,`categoria_id`,`ubicacion_id`,")
            lines.append("   `activo`,`es_sostenible`,`fecha_creacion`)")
            lines.append("VALUES")
    lines.append("")

    lines.append("-- 5. Metricas iniciales")
    lines.append("INSERT INTO `destino_metrica`")
    lines.append("  (`destino_id`,`calificacion_promedio`,`total_resenas`,")
    lines.append("   `afluencia`,`es_destino_saturado`,`fecha_actualizacion`)")
    lines.append("VALUES")
    for i in range(0, len(metrica_rows), BATCH):
        batch = metrica_rows[i:i+BATCH]
        if i + BATCH >= len(metrica_rows):
            lines.append(",\n".join(batch) + ";")
        else:
            lines.append(",\n".join(batch) + ";")
            lines.append("")
            lines.append("INSERT INTO `destino_metrica`")
            lines.append("  (`destino_id`,`calificacion_promedio`,`total_resenas`,")
            lines.append("   `afluencia`,`es_destino_saturado`,`fecha_actualizacion`)")
            lines.append("VALUES")
    lines.append("")
    lines.append("SET FOREIGN_KEY_CHECKS = 1;")
    lines.append("")
    lines.append(f"-- Fin del seed: {len(dest_rows)} destinos insertados")

    # Escribir archivo
    sql_content = "\n".join(lines)
    with open(OUTPUT_SQL, "w", encoding="utf-8") as f:
        f.write(sql_content)

    size_kb = OUTPUT_SQL.stat().st_size // 1024
    print(f"SQL generado: {OUTPUT_SQL}  ({size_kb} KB)", flush=True)
    print(f"  {len(cat_map)} categorias", flush=True)
    print(f"  {len(ubic_rows)} ubicaciones", flush=True)
    print(f"  {len(dest_rows)} destinos", flush=True)
    print(f"  {len(metrica_rows)} filas de metricas", flush=True)
    print(f"\nPara aplicar en MySQL:", flush=True)
    print(f"  mysql -u <usuario> -p explorachiapas < {OUTPUT_SQL}", flush=True)


def _icono_categoria(nombre: str) -> str:
    iconos = {
        "restaurante":           "restaurant",
        "cafe":                  "local_cafe",
        "bar":                   "sports_bar",
        "hotel":                 "hotel",
        "hostal":                "bed",
        "cabana":                "cabin",
        "campamento":            "camping",
        "museo":                 "museum",
        "zona arqueologica":     "account_balance",
        "monumento historico":   "account_balance",
        "monumento conmemorativo": "emoji_events",
        "iglesia / templo":      "church",
        "iglesia historica":     "church",
        "castillo / fuerte":     "castle",
        "parque":                "park",
        "reserva natural":       "nature",
        "area natural protegida":"forest",
        "jardin botanico":       "local_florist",
        "cascada":               "waterfall_chart",
        "manantial":             "water",
        "aguas termales":        "hot_tub",
        "cueva / cenote":        "terrain",
        "playa / laguna":        "beach_access",
        "montana / volcan":      "terrain",
        "mirador":               "landscape",
        "zoologico":             "cruelty_free",
        "parque tematico":       "attractions",
        "atractivo turistico":   "star",
        "mercado":               "storefront",
        "artesania":             "brush",
        "galeria de arte":       "palette",
        "galeria / arte":        "palette",
        "tienda de souvenirs":   "shopping_bag",
        "area de picnic":        "outdoor_grill",
        "punto de interes":      "place",
    }
    return iconos.get(nombre, "place")


if __name__ == "__main__":
    main()
