import csv
rows = []
with open("data/destinos.csv", encoding="utf-8", newline="") as f:
    r = csv.reader(f)
    h = next(r)
    for row in r:
        rows.append(row)
print(f"Total filas: {len(rows)}")
tenosique = [r for r in rows if r[3] == "Tenosique"]
print(f"Tenosique restantes: {len(tenosique)}")
destinos = [r for r in rows if r[2] == "destino"]
con_foto = [r for r in destinos if r[10].startswith("https")]
sin_foto = [r for r in destinos if not r[10].startswith("https")]
print(f"Destinos: {len(destinos)}, con foto: {len(con_foto)}, sin foto: {len(sin_foto)}")
