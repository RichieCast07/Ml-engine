"""
Busca en Wikimedia Commons una imagen para cada destino sin foto_url.
Estrategia:
  1. Busca foto específica del destino (nombre + municipio + Chiapas)
  2. Si no encuentra, usa foto del municipio (cache para no repetir llamadas)
  3. Si tampoco hay foto del municipio, deja vacío
"""
import csv, hashlib, time, urllib.parse, urllib.request, json

SRC   = "data/destinos.csv"
DST   = "data/destinos.csv"
API   = "https://commons.wikimedia.org/w/api.php"
DELAY = 0.3

# ── helpers ───────────────────────────────────────────────────────────────────

def thumb_url(filename, width=960):
    name = filename.replace(" ", "_")
    md5  = hashlib.md5(name.encode("utf-8")).hexdigest()
    h1, h2 = md5[0], md5[:2]
    enc  = urllib.parse.quote(name, safe="")
    return (
        f"https://upload.wikimedia.org/wikipedia/commons/thumb"
        f"/{h1}/{h2}/{enc}/{width}px-{enc}"
    )

def search_commons(query, tries=2):
    """Devuelve la URL del primer resultado válido de Commons, o None."""
    params = urllib.parse.urlencode({
        "action": "query", "list": "search",
        "srsearch": query, "srnamespace": "6",
        "srlimit": "5", "format": "json",
    })
    url = f"{API}?{params}"
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ExploraChiapas/1.0"})
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.loads(r.read())
            results = data.get("query", {}).get("search", [])
            for res in results:
                fname = res["title"].replace("File:", "").replace("file:", "")
                if not any(fname.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp")):
                    continue
                turl = thumb_url(fname)
                try:
                    chk = urllib.request.Request(turl, method="HEAD",
                                                 headers={"User-Agent": "ExploraChiapas/1.0"})
                    with urllib.request.urlopen(chk, timeout=5) as rc:
                        if rc.status == 200:
                            return turl
                except Exception:
                    continue
        except Exception:
            time.sleep(1)
    return None

# ── cache de fotos por municipio ──────────────────────────────────────────────
_muni_cache: dict[str, str] = {}

def foto_municipio(municipio: str) -> str | None:
    """Busca una foto representativa del municipio. Cachea el resultado."""
    if municipio in _muni_cache:
        return _muni_cache[municipio] or None

    for query in [
        f"{municipio} Chiapas Mexico",
        f"municipio {municipio} Chiapas",
        f"{municipio} Chiapas",
    ]:
        url = search_commons(query)
        time.sleep(DELAY)
        if url:
            _muni_cache[municipio] = url
            return url

    _muni_cache[municipio] = ""  # evitar re-buscar
    return None

# ── main ──────────────────────────────────────────────────────────────────────

def main():
    rows = []
    with open(SRC, encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            rows.append(row)

    for row in rows:
        while len(row) < 11:
            row.append("")

    sin_foto = [(i, r) for i, r in enumerate(rows)
                if not r[10].startswith("https") and r[2] == "destino"]

    print(f"Destinos sin foto: {len(sin_foto)}")
    encontrados = 0

    for n, (idx, row) in enumerate(sin_foto, 1):
        nombre    = row[1].strip()
        municipio = row[3].strip()

        # Intento 1 y 2: foto específica del destino
        url = None
        for query in [
            f"{nombre} {municipio} Chiapas",
            f"{nombre} Chiapas Mexico",
        ]:
            url = search_commons(query)
            time.sleep(DELAY)
            if url:
                break

        # Intento 3: foto del municipio
        if not url:
            url = foto_municipio(municipio)

        if url:
            row[10] = url
            encontrados += 1
            print(f"  [{n}/{len(sin_foto)}] OK  {nombre[:40]:<40} ({municipio})")
        else:
            print(f"  [{n}/{len(sin_foto)}] --  {nombre[:40]:<40} ({municipio})")

        if n % 50 == 0:
            _save(header, rows)
            print(f"  >> progreso guardado ({n} procesados, {encontrados} con foto)")

    _save(header, rows)
    print(f"\nListo: {encontrados}/{len(sin_foto)} destinos con nueva foto")

def _save(header, rows):
    with open(DST, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)

if __name__ == "__main__":
    main()
