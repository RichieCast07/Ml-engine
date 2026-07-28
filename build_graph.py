import json
import math
import time
import urllib.request

DATA_DIR    = "data"
COORDS_FILE = f"{DATA_DIR}/municipio_coords.json"
OUTPUT_FILE = f"{DATA_DIR}/grafo_municipios.json"

OSRM_BASE  = "https://router.project-osrm.org/table/v1/driving"
BLOCK_SIZE = 25

def factor(km):
    if km < 15:  return 1.4
    if km < 80:  return 1.1
    return 1.05

def haversine_km(lat1, lng1, lat2, lng2):
    r = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = (math.sin(d_lat/2)**2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(d_lng/2)**2)
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def fetch_block(src_indices, dst_indices, all_lnglat):
    # Construir lista de coordenadas unicas para esta llamada
    all_idx = list(dict.fromkeys(src_indices + dst_indices))  # preserva orden, sin duplicados
    idx_map = {global_i: local_i for local_i, global_i in enumerate(all_idx)}

    coords_str = ";".join(f"{all_lnglat[i][0]},{all_lnglat[i][1]}" for i in all_idx)
    sources_str = ";".join(str(idx_map[i]) for i in src_indices)
    dests_str   = ";".join(str(idx_map[i]) for i in dst_indices)

    url = (
        f"{OSRM_BASE}/{coords_str}"
        f"?sources={sources_str}&destinations={dests_str}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "ExploraChiapas/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())

def main():
    with open(COORDS_FILE, encoding="utf-8") as f:
        coords_raw = json.load(f)

    names  = list(coords_raw.keys())
    n      = len(names)
    lnglat = [(coords_raw[name]["lng"], coords_raw[name]["lat"]) for name in names]

    print(f"Municipios: {n}  —  pares únicos: {n*(n-1)//2}")

    # Distancias geodésicas con factor de tortuosidad 1.3 (terreno montañoso Chiapas)
    # Sirven como estimado de km reales de carretera cuando OSRM no da distancia
    lat = [coords_raw[name]["lat"] for name in names]
    lng = [coords_raw[name]["lng"] for name in names]

    geo_km = [[0.0]*n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i != j:
                geo_km[i][j] = round(haversine_km(lat[i], lng[i], lat[j], lng[j]) * 1.3, 1)

    # Matrices n×n inicializadas en None
    dur_min = [[None]*n for _ in range(n)]
    est_min = [[None]*n for _ in range(n)]
    for i in range(n):
        dur_min[i][i] = 0.0
        est_min[i][i] = 0

    # Crear bloques de índices
    blocks = [list(range(s, min(s + BLOCK_SIZE, n))) for s in range(0, n, BLOCK_SIZE)]
    total_calls = len(blocks) * len(blocks)
    call_n = 0

    for bi, src_block in enumerate(blocks):
        for bj, dst_block in enumerate(blocks):
            if bi > bj:
                # Usamos simetría: copiar desde el bloque (bj, bi) cuando esté listo
                continue
            call_n += 1
            print(f"  Bloque [{bi},{bj}] ({len(src_block)}×{len(dst_block)}) "
                  f"[{call_n}/{total_calls//2 + len(blocks)//2}]...", end=" ", flush=True)

            for attempt in range(3):
                try:
                    data = fetch_block(src_block, dst_block, lnglat)
                    break
                except Exception as e:
                    if attempt == 2:
                        print(f"ERROR: {e}")
                        data = None
                    else:
                        time.sleep(3)
            else:
                data = None

            if data is None:
                print("SKIP")
                continue

            durations = data.get("durations", [])
            distances = data.get("distances", [])

            for row_i, src_idx in enumerate(src_block):
                for col_j, dst_idx in enumerate(dst_block):
                    d_sec = durations[row_i][col_j] if durations else None
                    if d_sec is None:
                        continue
                    d_osrm_min = round(d_sec / 60, 1)
                    d_km_val   = geo_km[src_idx][dst_idx]  # geodésico×1.3
                    f          = factor(d_km_val)
                    d_est      = int(round(d_osrm_min * f))

                    dur_min[src_idx][dst_idx] = d_osrm_min
                    est_min[src_idx][dst_idx] = d_est

                    if dur_min[dst_idx][src_idx] is None:
                        dur_min[dst_idx][src_idx] = d_osrm_min
                        est_min[dst_idx][src_idx] = d_est

            print("OK")
            time.sleep(0.8)

    # Lista de aristas (triángulo superior)
    edges = []
    for i in range(n):
        for j in range(i+1, n):
            if dur_min[i][j] is None:
                continue
            edges.append({
                "from":     names[i],
                "to":       names[j],
                "geo_km":   geo_km[i][j],
                "osrm_min": dur_min[i][j],
                "factor":   factor(geo_km[i][j]),
                "est_min":  est_min[i][j],
            })

    grafo = {
        "_meta": {
            "nodos": n,
            "aristas": len(edges),
            "fuente": "OSRM router.project-osrm.org (driving) + Haversine×1.3",
            "factores_correccion": {
                "menor_15km": 1.4,
                "entre_15_80km": 1.1,
                "mayor_80km": 1.05
            },
            "nota_distancias": "geo_km = distancia geodésica × 1.3 (tortuosidad Chiapas). est_min = osrm_min × factor."
        },
        "municipios": names,
        "edges": edges,
        "geo_km":       geo_km,
        "dur_osrm_min": dur_min,
        "est_min":      est_min,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(grafo, f, ensure_ascii=False, separators=(",", ":"))

    print(f"\nGuardado: {OUTPUT_FILE}")
    print(f"  {n} municipios, {len(edges)} aristas")

if __name__ == "__main__":
    main()
