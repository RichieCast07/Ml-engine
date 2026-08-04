import csv

SRC = "data/destinos.csv"

ELIMINAR_IDS = {
    "19","20","21","24","25","37","38","40","66","154","234",
    "245","246","247","248","249","250","251","252","253","254",
    "255","256","257","258","259","315","358","359","360","361",
    "362","363","364","367","368","369","370","371","372","373",
    "374","375","376","377","561",
    "690","768","902","903","1217","1231",
    "87","88","89","90","91","92","93","94","105","480","564","574",
    "68","69",
    "128","132","137","276","428","494","503","506","507","566",
    "3","13",
    "18","147","229","263",
    "99","149","182","457","262","496",
    "41","227","238","277","297","319","596","423",
}

CORREGIR_NOMBRE = {
    "32":  "Mirador Roblar",
    "134": "Poza Natural de Mapastepec",
    "220": "Arte Urbano San Cristobal de las Casas",
}

CORREGIR_MUNICIPIO_ID = {
    "317": "Ocosingo", "323": "Ocosingo",
    "517": "Ocosingo", "518": "Ocosingo",
    "519": "Ocosingo", "520": "Ocosingo", "521": "Ocosingo",
}

rows = []
with open(SRC, encoding="utf-8", newline="") as f:
    reader = csv.reader(f)
    header = next(reader)
    for row in reader:
        while len(row) < 11:
            row.append("")
        rows.append(row)

print(f"Filas originales: {len(rows)}")
eliminados = renombrados = muni_fix = 0
limpias = []

for row in rows:
    rid = row[0].strip()
    if rid in ELIMINAR_IDS:
        eliminados += 1
        continue
    if rid in CORREGIR_NOMBRE:
        viejo = row[1]
        row[1] = CORREGIR_NOMBRE[rid]
        print(f"  NOMBRE  {rid}: {repr(viejo)} -> {repr(row[1])}")
        renombrados += 1
    if rid in CORREGIR_MUNICIPIO_ID:
        viejo = row[3]
        row[3] = CORREGIR_MUNICIPIO_ID[rid]
        print(f"  MUNI    {rid}: {repr(viejo)} -> {repr(row[3])}")
        muni_fix += 1
    muni = row[3].strip()
    if muni == "Tumbala":
        row[3] = "Tumbala"
        muni_fix += 1
    elif muni == "Chamula":
        row[3] = "San Juan Chamula"
        muni_fix += 1
    elif muni == "Ocozocoautla":
        row[3] = "Ocozocoautla de Espinosa"
        muni_fix += 1
    limpias.append(row)

print(f"Eliminados: {eliminados}")
print(f"Renombrados: {renombrados}")
print(f"Municipios fijos: {muni_fix}")
print(f"Filas finales: {len(limpias)}")

with open("data/destinos.csv", "w", encoding="utf-8", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(header)
    writer.writerows(limpias)
print("Guardado OK.")
