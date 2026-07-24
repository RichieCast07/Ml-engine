"""
Aplica update_imagenes.sql en Supabase usando queries parametrizadas.
Parsea el SQL generado y ejecuta con psycopg2 para evitar problemas de escaping.
Uso: python scripts/apply_imagenes.py
"""

import re
from pathlib import Path

SQL_FILE = Path("scripts/update_imagenes.sql")

HOST     = "aws-0-us-east-1.pooler.supabase.com"
PORT     = 5432
USER     = "postgres.xarpdhylleopgcjattbu"
PASSWORD = "QAZejdncncue123da?=8e++}\"123\""
DBNAME   = "postgres"

# Captura URL y nombre ignorando los escapes de MySQL dentro de las cadenas
PATRON = re.compile(
    r"UPDATE destino SET imagen_url = '((?:[^'\\]|\\.)*)' "
    r"WHERE LOWER\(nombre\) = LOWER\('((?:[^'\\]|\\.)*)'\);"
)


def unescape(s: str) -> str:
    """Convierte escaping MySQL (\' y \\) a string Python."""
    return s.replace("\\'", "'").replace("\\\\", "\\")


def main():
    try:
        import psycopg2
    except ImportError:
        import subprocess, sys
        subprocess.check_call([sys.executable, "-m", "pip", "install", "psycopg2-binary"])
        import psycopg2

    sql = SQL_FILE.read_text(encoding="utf-8")
    filas = [(unescape(m.group(1)), unescape(m.group(2))) for m in PATRON.finditer(sql)]
    print(f"Filas a actualizar: {len(filas)}")

    print(f"Conectando a {HOST}:{PORT}...")
    conn = psycopg2.connect(
        host=HOST, port=PORT, user=USER,
        password=PASSWORD, dbname=DBNAME,
        sslmode="require", connect_timeout=15,
    )
    conn.autocommit = False
    cur = conn.cursor()

    BATCH = 500
    total_actualizadas = 0
    for i in range(0, len(filas), BATCH):
        batch = filas[i:i+BATCH]
        for url, nombre in batch:
            cur.execute(
                "UPDATE destino SET imagen_url = %s WHERE LOWER(nombre) = LOWER(%s)",
                (url, nombre),
            )
            total_actualizadas += cur.rowcount
        conn.commit()
        print(f"  Procesadas {min(i+BATCH, len(filas))}/{len(filas)} (actualizadas hasta ahora: {total_actualizadas})")

    cur.execute("SELECT COUNT(*) FROM destino WHERE imagen_url IS NOT NULL")
    con_imagen = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM destino")
    total = cur.fetchone()[0]

    cur.close()
    conn.close()
    print(f"\nListo.")
    print(f"  Filas actualizadas en esta ejecucion: {total_actualizadas}")
    print(f"  Destinos con imagen_url en DB: {con_imagen}/{total}")


if __name__ == "__main__":
    main()
