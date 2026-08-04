"""
Limpieza quirurgica de destinos.csv:
  1. Elimina entradas de Tenosique (Tabasco, no Chiapas)
  2. Reasigna Yaxchilan y Bonampak a Ocosingo, Chiapas
  3. Elimina entradas no turisticas (infraestructura, areas verdes, placeholders)
  4. Elimina duplicados
  5. Corrige nombres en otros idiomas y nombres mal escritos
  6. Unifica nombres de municipios inconsistentes
  7. Verifica URLs de fotos existentes
"""
import csv, hashlib, urllib.parse, urllib.request, json, time

SRC = "data/destinos.csv"
DST = "data/destinos.csv"

ELIMINAR_IDS = {
    # ─── TENOSIQUE (municipio de TABASCO, no Chiapas) ───────────────────────
    "19",   # Estela 11
    "20",   # Estela 3
    "21",   # Gran Acropolis
    "24",   # Pequeña Acropolis
    "25",   # La Gran Plaza
    "37",   # Lakan'Ha
    "38",   # Cascadas de Santo Domingo (Tabasco)
    "40",   # Estela 1
    "66",   # Zona Arqueologica Yaxchilan (duplicado de 317; 317 se reasigna)
    "154",  # Parque Natural Monte Azul (Tabasco)
    "234",  # Temple sacrificiel Maya (frances)
    "245",  # Noh K'uh
    "246",  # La Punta
    "247",  # Tzunun
    "248",  # Tz'ib'ana
    "249",  # Munic Na
    "250",  # Xtabay
    "251",  # Chak Ak Tun
    "252",  # Kuh Nabaat
    "253",  # Kakoch
    "254",  # Mensabak
    "255",  # Sakapuk
    "256",  # Sak Tat
    "257",  # Kinbor
    "258",  # Joton K'ak
    "259",  # Aj Chaj Chi
    "315",  # Plan de Ayutla (Tabasco)
    "358",  # Edificio 1 - de las Pinturas (ya cubierto por Bonampak)
    "359",  # Escala
    "360",  # Acropolis
    "361",  # Templo (demasiado generico)
    "362",  # Edificio 33
    "363",  # Edificio 12
    "364",  # Edificio 14 (Juego de Pelota)
    "367",  # Edificio 16
    "368",  # Edificio 39
    "369",  # Edificio 40
    "370",  # Edificio 41
    "371",  # El Laberinto - Edificio 19
    "372",  # Edificio 17
    "373",  # Edificio 20
    "374",  # Edificio 21
    "375",  # Edificio 22
    "376",  # Edificio23
    "377",  # Edificio 24
    "561",  # Acropolis Sur
    # Restaurantes en Tenosique (Tabasco)
    "690",  "768",  "902",  "903",  "1217", "1231",

    # ─── AREAS VERDES GENERICAS / ESPACIOS SIN NOMBRE ───────────────────────
    "87",   # trees
    "88",   # open grass field
    "89",   # open land with some trees
    "90",   # Open tree area
    "91",   # open tree area (duplicado)
    "92",   # Open Tree Area (duplicado)
    "93",   # Open Field Area
    "94",   # Open Tree
    "105",  # Open Area
    "480",  # estacionamiento con parque
    "564",  # Zona verde, Zona con muchos arboles
    "574",  # Area verde con bancas (no aparece en lista pero existia)

    # ─── PLACEHOLDERS ────────────────────────────────────────────────────────
    "68",   # nom_parque
    "69",   # nom_recinto

    # ─── INFRAESTRUCTURA / SERVICIOS PUBLICOS (no turisticos) ───────────────
    "128",  # Pilares CFE
    "132",  # Bancrisa
    "137",  # Cancha Basquetball
    "276",  # Cancha La Pista (Simojovel)
    "428",  # Zona boscosa 24 Pte
    "494",  # IMSS
    "503",  # CEDECO Estacion Ferroviaria
    "506",  # Campo Moscafrut
    "507",  # Estacionamiento D. Metodos
    "566",  # Parque Industrial Los Rios

    # ─── CLUBES / RECINTOS PRIVADOS ─────────────────────────────────────────
    "3",    # Club Campestre
    "13",   # Club Leones

    # ─── NOMBRES EN IDIOMA EXTRANJERO ────────────────────────────────────────
    "18",   # Wasserfall (aleman; ya existe Misol-Ha correctamente)
    "147",  # Batshit Cave
    "229",  # Hidden temple entrance under tree
    "263",  # Three Monkeys (nombre en ingles; no es lugar turistico identificado)

    # ─── NEGOCIOS / NO DESTINOS TURISTICOS ──────────────────────────────────
    "99",   # Beau Degat [bo.de.ga] (bar/galeria privado)
    "149",  # Steps (non-profit with workshops)
    "182",  # STEPS nonprofit
    "457",  # Parque infantil privado de la Iglesia
    "262",  # Col. 16 de Septiembre (barrio residencial)
    "496",  # Water Blue (demasiado vago)

    # ─── DUPLICADOS ──────────────────────────────────────────────────────────
    "41",   # Cruz (Berriozabal) — demasiado generico
    "227",  # Arco Del Tiempo (Cintalapa) = duplicado de 169
    "238",  # Arco Carmen = Arco del Carmen (ya existe con buen nombre)
    "277",  # Street-art = Street art (220 renombrado)
    "297",  # Street Art = Street art (220 renombrado)
    "319",  # Mision Surf Mexico = duplicado de 177
    "596",  # Museo Na Bolom = Na Bolom (6)
    "423",  # Parque "Bancrisa" — parque llamado igual que el banco, confuso
}

# Correcciones de nombre (ID → nombre correcto)
CORREGIR_NOMBRE = {
    "32":  "Mirador Roblar",
    "134": "Poza Natural de Mapastepec",
    "220": "Arte Urbano San Cristobal de las Casas",
}

# Correcciones de municipio por ID especifico
CORREGIR_MUNICIPIO_ID = {
    "317": "Ocosingo",  # Zona arqueologica de Yaxchilan
    "323": "Ocosingo",  # Zona arqueologica de Bonampak
    "517": "Ocosingo",  # Area de Proteccion Flora y Fauna Naha
    "518": "Ocosingo",  # Area de Proteccion Flora y Fauna Metzabok
    "519": "Ocosingo",  # Monumento Natural Yaxchilan
    "520": "Ocosingo",  # Area de Proteccion Flora y Fauna Chan-Kin
    "521": "Ocosingo",  # Monumento Natural Bonampak
}

def verificar_url(url, timeout=6):
    if not url or not url.startswith("https"):
        return False
    try:
        req = urllib.request.Request(
            url, method="HEAD", headers={"User-Agent": "ExploraChiapas/1.0"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False

def main():
    rows = []
    with open(SRC, encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            while len(row) < 11:
                row.append("")
            rows.append(row)

    print(f"Filas originales: {len(rows)}")

    eliminados = renombrados = muni_fix = foto_fix = 0
    limpias = []

    for row in rows:
        rid = row[0].strip()

        if rid in ELIMINAR_IDS:
            eliminados += 1
            continue

        if rid in CORREGIR_NOMBRE:
            viejo = row[1]
            row[1] = CORREGIR_NOMBRE[rid]
            print(f"  NOMBRE  {rid:5s}: '{viejo}' -> '{row[1]}'")
            renombrados += 1

        if rid in CORREGIR_MUNICIPIO_ID:
            viejo = row[3]
            row[3] = CORREGIR_MUNICIPIO_ID[rid]
            print(f"  MUNI    {rid:5s}: '{viejo}' -> '{row[3]}'")
            muni_fix += 1

        muni = row[3].strip()
        if muni == "Tumbala":
            row[3] = "Tumbalá"
            muni_fix += 1
        elif muni == "Chamula":
            row[3] = "San Juan Chamula"
            muni_fix += 1
        elif muni == "Ocozocoautla":
            row[3] = "Ocozocoautla de Espinosa"
            muni_fix += 1

        if row[10].startswith("https") and row[2] == "destino":
            if not verificar_url(row[10]):
                print(f"  FOTO-X  {rid:5s}: URL invalida -> {row[1][:40]}")
                row[10] = ""
                foto_fix += 1
            time.sleep(0.1)

        limpias.append(row)

    print(f"\nResumen:")
    print(f"  Eliminados:       {eliminados}")
    print(f"  Renombrados:      {renombrados}")
    print(f"  Municipios fijos: {muni_fix}")
    print(f"  Fotos invalidas:  {foto_fix}")
    print(f"  Filas finales:    {len(limpias)}")

    with open(DST, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(limpias)

    print(f"\nGuardado: {DST}")

if __name__ == "__main__":
    main()
