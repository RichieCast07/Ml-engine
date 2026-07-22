"""
Filtra destinos_reales.csv para conservar solo los 124 municipios de Chiapas.
Elimina lugares de Guatemala, Tabasco y otros estados que se colaron por el bounding box.

Uso:
  python3 scripts/filtrar_chiapas.py
"""

import csv
from pathlib import Path

MUNICIPIOS_CHIAPAS = {
    "Acacoyagua", "Acala", "Acapetahua", "Altamirano", "Amatán",
    "Amatenango de la Frontera", "Amatenango del Valle", "Ángel Albino Corzo",
    "Arriaga", "Bejucal de Ocampo", "Bella Vista", "Berriozábal", "Bochil",
    "Cacahoatán", "Catazajá", "Cintalapa", "Coapilla", "Comitán de Domínguez",
    "Copainalá", "Chalchihuitán", "Chamula", "Chanal", "Chapultenango",
    "Chenalhó", "Chiapa de Corzo", "Chiapilla", "Chicoasén", "Chicomuselo",
    "Chilón", "Escuintla", "Frontera Comalapa", "Frontera Hidalgo",
    "La Grandeza", "Huehuetán", "Huixtán", "Huitiupán", "Huixtla",
    "La Independencia", "Ixhuatán", "Ixtacomitán", "Ixtapa", "Ixtapangajoya",
    "Jiquipilas", "Jitotol", "Juárez", "Larráinzar", "La Libertad",
    "Mapastepec", "Las Margaritas", "Maravilla Tenejapa", "Marqués de Comillas",
    "Mazapa de Madero", "Mazatán", "Metapa", "Mezcalapa", "Mitontic",
    "Motozintla", "La Trinitaria", "Nicolás Ruíz", "Ocosingo", "Ocotepec",
    "Ocozocoautla de Espinosa", "Ostuacán", "Osumacinta", "Oxchuc", "Palenque",
    "Pantelhó", "Pantepec", "Pichucalco", "Pijijiapan", "El Porvenir",
    "Villa de las Rosas", "Pueblo Nuevo Solistahuacán", "Rayón", "Reforma",
    "Las Rosas", "Sabanilla", "Salto de Agua", "San Andrés Duraznal",
    "San Cristóbal de las Casas", "San Fernando", "San Juan Cancuc",
    "San Lucas", "San Marcos", "Santiago el Pinar", "Siltepec", "Simojovel",
    "Sitalá", "Solosuchiapa", "Socoltenango", "Soyaló", "Suchiapa",
    "Suchiate", "Sunuapa", "Tapalapa", "Tapachula", "Tecpatán", "Tenejapa",
    "Teopisca", "Tila", "Tonalá", "Totolapa", "Tumbala", "Tuxtla Chico",
    "Tuxtla Gutiérrez", "Tuzantán", "Tzimol", "Unión Juárez",
    "Venustiano Carranza", "Villa Comaltitlán", "Villaflores", "Yajalón",
    "Zinacantán",
}

IN_CSV  = Path("data/destinos_reales.csv")
OUT_CSV = Path("data/destinos.csv")

def main():
    if not IN_CSV.exists():
        print(f"ERROR: no existe {IN_CSV}")
        return

    total = rechazados = aceptados = 0
    municipios_no_chiapas = set()

    with open(IN_CSV, encoding="utf-8", newline="") as f_in, \
         open(OUT_CSV, "w", encoding="utf-8", newline="") as f_out:

        reader = csv.DictReader(f_in)
        writer = csv.DictWriter(f_out, fieldnames=reader.fieldnames)
        writer.writeheader()

        for fila in reader:
            total += 1
            muni = fila.get("municipio", "").strip()
            if muni in MUNICIPIOS_CHIAPAS:
                # Reasignar IDs correlativos
                fila["id"] = aceptados + 1
                writer.writerow(fila)
                aceptados += 1
            else:
                rechazados += 1
                municipios_no_chiapas.add(muni)

    con_foto = 0
    with open(OUT_CSV, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("foto_url", "").strip():
                con_foto += 1

    print(f"Total leídos:      {total}")
    print(f"Aceptados (Chiapas): {aceptados}")
    print(f"Rechazados:          {rechazados}")
    print(f"Con foto:            {con_foto}")
    print()
    print(f"Guardado en: {OUT_CSV}")
    print()
    if municipios_no_chiapas:
        print("Municipios descartados:")
        for m in sorted(municipios_no_chiapas):
            print(f"  - {m}")

if __name__ == "__main__":
    main()
