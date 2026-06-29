"""
Genera datos sinteticos de historial de visitas (transacciones de categorias
co-visitadas) para alimentar el algoritmo de reglas de asociacion (Apriori).

Estos datos son un placeholder deliberado: el sistema real todavia no tiene
usuarios generando historial, asi que se simulan patrones de afinidad
plausibles (ej. quien visita naturaleza tiende a comer despues, quien hace
aventura tiende a tomar fotos) con una semilla fija para que el resultado sea
reproducible. Cuando la app este en produccion, este archivo debe sustituirse
por el historial real de itinerarios guardados en la base de datos.
"""

import json
import random
from pathlib import Path

random.seed(42)

CATEGORIAS = [
    "naturaleza", "cultura", "gastronomia", "aventura",
    "familiar", "descanso", "fotografia", "eventos",
]

# Pares con afinidad alta: aparecen juntos con mayor probabilidad.
AFINIDADES = [
    ("naturaleza", "gastronomia", 0.55),
    ("aventura", "fotografia", 0.5),
    ("cultura", "gastronomia", 0.5),
    ("familiar", "descanso", 0.45),
    ("eventos", "gastronomia", 0.4),
    ("aventura", "naturaleza", 0.4),
    ("fotografia", "cultura", 0.35),
]

N_TRANSACCIONES = 200


def generar_transaccion() -> list[str]:
    categoria_base = random.choice(CATEGORIAS)
    transaccion = {categoria_base}

    for a, b, prob in AFINIDADES:
        if categoria_base == a and random.random() < prob:
            transaccion.add(b)
        elif categoria_base == b and random.random() < prob:
            transaccion.add(a)

    # ruido: a veces se agrega una tercera categoria sin relacion clara
    if random.random() < 0.2:
        transaccion.add(random.choice(CATEGORIAS))

    return sorted(transaccion)


def main() -> None:
    transacciones = [generar_transaccion() for _ in range(N_TRANSACCIONES)]
    salida = Path(__file__).resolve().parent.parent / "data" / "historial_visitas.json"
    salida.write_text(json.dumps(transacciones, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Generadas {len(transacciones)} transacciones sinteticas en {salida}")


if __name__ == "__main__":
    main()
