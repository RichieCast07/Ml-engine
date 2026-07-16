"""
Genera el dataset completo para el motor ML de ExploraChiapas.

Produce:
  data/destinos.csv          -- 20,000 destinos + 20,000 restaurantes = 40,000 registros
  data/historial_visitas.csv -- 200,000 transacciones de visitas

Uso:
  python scripts/generate_dataset.py
"""

import csv
import random
from pathlib import Path

random.seed(42)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# ─── 56 municipios de Chiapas con turismo ────────────────────────────────────
MUNICIPIOS = [
    "Tuxtla Gutierrez", "San Cristobal de las Casas", "Palenque", "Tapachula",
    "Ocosingo", "Comitan de Dominguez", "Chiapa de Corzo", "Tonala",
    "La Trinitaria", "Tzimol", "Berriozabal", "Suchiapa", "Ocozocoautla",
    "Soyalo", "Pueblo Nuevo Solistahaucan", "La Independencia", "Villaflores",
    "Arriaga", "Pichucalco", "Yajalon", "Tila", "Simojovel", "Huixtla",
    "Venustiano Carranza", "Las Margaritas", "Motozintla", "Siltepec",
    "Tumbala", "Salto de Agua", "San Juan Chamula", "Zinacantlan",
    "Angel Albino Corzo", "Tenosique", "La Concordia", "Mapastepec",
    "Pijijiapan", "Acapetahua", "Villa Corzo", "Jiquipilas", "Bochil",
    "San Fernando", "Pantelho", "Chilon", "Socoltenango", "Tenejapa",
    "Amatenango del Valle", "La Paz", "Frontera Comalapa", "Escuintla",
    "Acacoyagua", "Huehuetan", "Ixtacomitan", "Reforma", "Ostuacan",
    "Cintalapa", "Juchitan",
]

# ─── Plantillas de nombres para destinos ─────────────────────────────────────
# Cada categoria tiene listas de prefijos y sufijos que se combinan
# para generar nombres unicos y plausibles.

PLANTILLAS = {
    "naturaleza": {
        "prefijos": [
            "Cascada", "Parque Natural", "Sendero Ecologico", "Laguna",
            "Reserva Natural", "Cerro", "Rio", "Mirador Natural",
            "Zona de Conservacion", "Manantial", "Barranca", "Valle Natural",
            "Bosque Comunitario", "Poza Natural", "Cueva",
        ],
        "sufijos": [
            "El Quetzal", "Las Orquideas", "El Jaguar", "Los Monos",
            "El Colibri", "Las Aves", "El Copal", "Las Mariposas",
            "El Cedro", "Los Tapires", "La Niebla", "El Bosque Humedo",
            "Los Pericos", "El Rio Cristal", "Las Luciernagas",
            "El Caiman", "Las Palmas", "Los Helechos", "La Bruma",
            "El Capulin",
        ],
        "n_total": 30000,
    },
    "cultura": {
        "prefijos": [
            "Museo", "Centro Cultural", "Zona Arqueologica", "Barrio Historico",
            "Hacienda Colonial", "Templo", "Galeria de Arte", "Casa Museo",
            "Sitio Patrimonial", "Mercado Artesanal", "Convento",
            "Palacio Historico", "Centro Comunitario",
        ],
        "sufijos": [
            "de la Herencia Maya", "del Pueblo Chiapaneco", "de las Tradiciones",
            "de la Memoria", "del Arte Local", "de los Ancestros",
            "del Territorio Indigena", "de la Identidad", "del Tiempo Antiguo",
            "del Patrimonio", "del Coleto", "de las Raices",
            "de la Historia", "del Tejido", "de las Culturas Vivas",
        ],
        "n_total": 28000,
    },
    "gastronomia": {
        "prefijos": [
            "Ruta Gastronomica", "Mercado de Sabores", "Cooperativa Culinaria",
            "Taller de Cocina Tradicional", "Centro Gastronomico",
            "Sendero del", "Festival del", "Feria de la",
        ],
        "sufijos": [
            "Cocina Chiapaneca", "Cafe de Altura", "Chile y Especias",
            "Chocolate Artesanal", "Mole Chiapaneco", "Tamal Regional",
            "Comida de Selva", "Trucha Ahumada", "Cacao y Vainilla",
            "Pan de Yema", "Queso Chiapaneco", "Pozol Tradicional",
            "Atole de Granillo", "Pox Artesanal", "Tamales de Chipilin",
            "Cecina Regional", "Cochito al Horno", "Sopa de Pan",
        ],
        "n_total": 24000,
    },
    "aventura": {
        "prefijos": [
            "Senderismo Extremo", "Tirolesa", "Rafting", "Rappel",
            "Kayak", "Ciclismo de Montana", "Escalada", "Espeleologia",
            "Parapente", "Canyoning", "Canopy", "Campamento de Aventura",
            "Travesia de Montana", "Expedicion", "Cabalgata de Aventura",
        ],
        "sufijos": [
            "en Canada Profunda", "en Rio Salvaje", "en Barranca",
            "en Sierra Nevada", "en Selva Humeda", "en Cascadas",
            "en Cueva Oscura", "en Acantilado", "en Montana Alta",
            "en Bosque Nublado", "en Rio Rapido", "en Valle Profundo",
            "en Roca Viva", "en Zona Extrema", "en Frontera Natural",
        ],
        "n_total": 30000,
    },
    "familiar": {
        "prefijos": [
            "Parque Familiar", "Balneario", "Centro Recreativo",
            "Jardin Familiar", "Rancho Didactico", "Granja Ecologica",
            "Parque Infantil", "Camping Familiar", "Area de Picnic",
            "Finca Educativa", "Parque Acuatico",
        ],
        "sufijos": [
            "Las Estrellas", "Los Ninos", "El Arco Iris", "El Sol",
            "La Luna", "Los Suenos", "La Diversion", "El Juego",
            "La Naturaleza Viva", "Los Colores", "El Aire Libre",
            "La Alegria", "El Prado Verde",
        ],
        "n_total": 26000,
    },
    "descanso": {
        "prefijos": [
            "Spa", "Retiro de Bienestar", "Cabanas de Descanso", "Glamping",
            "Hacienda de Retiro", "Centro de Meditacion", "Posada Rural",
            "Rancho de Descanso", "Eco-Retiro",
        ],
        "sufijos": [
            "Entre Montanas", "En La Selva", "Al Borde del Rio",
            "Con Vista al Valle", "En Silencio Natural", "Entre Ceibas",
            "Con Aguas Termales", "Al Amanecer", "En Paz y Quietud",
            "En El Bosque", "Bajo Las Estrellas",
        ],
        "n_total": 22000,
    },
    "fotografia": {
        "prefijos": [
            "Mirador", "Ruta Fotografica", "Punto de Vista", "Ventana Natural",
            "Panoramica", "Observatorio Natural", "Andador Fotografico",
        ],
        "sufijos": [
            "del Horizonte Verde", "del Canon", "de las Cascadas",
            "del Valle Brumoso", "de la Selva", "del Atardecer Chiapaneco",
            "del Lago Esmeralda", "de la Arquitectura Colonial",
            "del Cielo y La Tierra", "del Amanecer Mistico",
            "de la Comunidad Indigena", "del Rio entre Piedras",
        ],
        "n_total": 22000,
    },
    "eventos": {
        "prefijos": [
            "Festival", "Feria", "Carnaval", "Encuentro Cultural",
            "Noche de", "Semana de", "Expo", "Congreso Cultural de",
        ],
        "sufijos": [
            "La Marimba Chiapaneca", "El Cafe de Altura", "La Cultura Maya",
            "Las Tradiciones", "El Arte Popular", "La Gastronomia Regional",
            "Los Artesanos", "La Cosecha del Cacao", "La Danza Folklorica",
            "Las Flores Silvestres", "El Tejido Indigena", "Los Sabores",
            "La Musica de Chiapas", "Los Pueblos Originarios",
        ],
        "n_total": 18000,
    },
}

# Verificacion: la suma de n_total debe sumar 200,000
assert sum(v["n_total"] for v in PLANTILLAS.values()) == 200000, "La suma de destinos debe ser 200,000"

# ─── Tipos de comida para restaurantes ───────────────────────────────────────
TIPOS_COMIDA = [
    "comida tradicional chiapaneca",
    "carne asada",
    "mariscos",
    "antojitos",
    "cafe y postres",
    "comida internacional",
    "comida vegetariana",
    "mariscos y pescados",
    "cocina de autor",
    "sushi y comida oriental",
    "panaderia artesanal",
    "comida de mar",
]

PREFIJOS_RESTAURANTE = [
    "El Sabor de", "La Cocina de", "Fonda", "Restaurante",
    "Marisqueria", "Asadero", "Taqueria", "Cafeteria",
    "Comedor", "Parrilla", "El Fogon de", "Antojeria",
    "Loncheria", "Cafe", "La Sazon de", "Bistro",
    "El Rincon de", "La Tradicion de", "La Mesa de", "El Guiso de",
]

ADJETIVOS_RESTAURANTE = [
    "Tradicional", "Chiapaneco", "Regional", "Artesanal",
    "Colonial", "Familiar", "Popular", "Autentico",
    "Organico", "Sustentable", "Local", "Natural",
    "Gourmet", "Casero", "Rustico",
]

N_RESTAURANTES = 200000

# ─── Distribuciones de afluencia/costo por cluster ───────────────────────────
CLUSTER_SPECS = {
    "saturado":        {"afl_min": 8000,  "afl_max": 22000, "costo_min": 0,   "costo_max": 200},
    "moderado":        {"afl_min": 1500,  "afl_max": 8000,  "costo_min": 20,  "costo_max": 300},
    "potencial_oculto":{"afl_min": 200,   "afl_max": 1500,  "costo_min": 150, "costo_max": 500},
}

# Probabilidades de caer en cada cluster segun la categoria del destino
PROB_CLUSTER = {
    "naturaleza":  {"saturado": 0.20, "moderado": 0.55, "potencial_oculto": 0.25},
    "cultura":     {"saturado": 0.25, "moderado": 0.55, "potencial_oculto": 0.20},
    "gastronomia": {"saturado": 0.30, "moderado": 0.50, "potencial_oculto": 0.20},
    "aventura":    {"saturado": 0.05, "moderado": 0.40, "potencial_oculto": 0.55},
    "familiar":    {"saturado": 0.30, "moderado": 0.55, "potencial_oculto": 0.15},
    "descanso":    {"saturado": 0.10, "moderado": 0.40, "potencial_oculto": 0.50},
    "fotografia":  {"saturado": 0.35, "moderado": 0.50, "potencial_oculto": 0.15},
    "eventos":     {"saturado": 0.30, "moderado": 0.50, "potencial_oculto": 0.20},
    "restaurante": {"saturado": 0.20, "moderado": 0.55, "potencial_oculto": 0.25},
}


def elegir_cluster(categoria):
    probs = PROB_CLUSTER.get(categoria, PROB_CLUSTER["restaurante"])
    opciones = list(probs.keys())
    pesos = list(probs.values())
    return random.choices(opciones, weights=pesos, k=1)[0]


def generar_caracteristicas(cluster):
    spec = CLUSTER_SPECS[cluster]
    afluencia = random.randint(spec["afl_min"], spec["afl_max"])
    costo = random.randint(spec["costo_min"], spec["costo_max"])
    return afluencia, costo


def generar_nombre_destino(categoria, municipio, contador):
    """Combina prefijo + sufijo + municipio + variante numerica si es necesario."""
    config = PLANTILLAS[categoria]
    prefijos = config["prefijos"]
    sufijos = config["sufijos"]
    prefijo = prefijos[contador % len(prefijos)]
    sufijo = sufijos[(contador // len(prefijos)) % len(sufijos)]
    variante = contador // (len(prefijos) * len(sufijos))
    if variante == 0:
        return f"{prefijo} {sufijo} ({municipio})"
    return f"{prefijo} {sufijo} {variante + 1} ({municipio})"


def generar_nombre_restaurante(tipo_comida, municipio, contador):
    """Genera nombre de restaurante unico a partir de plantillas."""
    prefijo = PREFIJOS_RESTAURANTE[contador % len(PREFIJOS_RESTAURANTE)]
    adjetivo = ADJETIVOS_RESTAURANTE[(contador // len(PREFIJOS_RESTAURANTE)) % len(ADJETIVOS_RESTAURANTE)]
    variante = contador // (len(PREFIJOS_RESTAURANTE) * len(ADJETIVOS_RESTAURANTE))
    if variante == 0:
        return f"{prefijo} {adjetivo} ({municipio})"
    return f"{prefijo} {adjetivo} {variante + 1} ({municipio})"


# ─── Generacion de los 20,000 destinos ───────────────────────────────────────

def generar_destinos():
    registros = []
    id_actual = 1
    mun_cycle = list(MUNICIPIOS)
    random.shuffle(mun_cycle)

    for categoria, config in PLANTILLAS.items():
        n = config["n_total"]
        tiempo_base = {"naturaleza": 3, "cultura": 2, "gastronomia": 2,
                       "aventura": 4, "familiar": 3, "descanso": 3,
                       "fotografia": 2, "eventos": 3}.get(categoria, 3)

        for contador in range(n):
            municipio = mun_cycle[contador % len(mun_cycle)]
            nombre = generar_nombre_destino(categoria, municipio, contador)
            cluster = elegir_cluster(categoria)
            afluencia, costo = generar_caracteristicas(cluster)
            tiempo = tiempo_base + random.choice([-1, 0, 0, 1])
            tiempo = max(1, min(5, tiempo))

            registros.append({
                "id": id_actual,
                "nombre": nombre,
                "tipo": "destino",
                "municipio": municipio,
                "categoria": categoria,
                "tipo_comida": "",
                "costo_estimado": costo,
                "tiempo_horas": tiempo,
                "nivel_afluencia": afluencia,
            })
            id_actual += 1

    return registros, id_actual


# ─── Generacion de los 20,000 restaurantes ───────────────────────────────────

def generar_restaurantes(id_inicio):
    registros = []
    id_actual = id_inicio
    mun_cycle = list(MUNICIPIOS)
    random.shuffle(mun_cycle)

    for contador in range(N_RESTAURANTES):
        municipio = mun_cycle[contador % len(mun_cycle)]
        tipo_comida = TIPOS_COMIDA[contador % len(TIPOS_COMIDA)]
        nombre = generar_nombre_restaurante(tipo_comida, municipio, contador)
        cluster = elegir_cluster("restaurante")
        afluencia, costo = generar_caracteristicas(cluster)

        registros.append({
            "id": id_actual,
            "nombre": nombre,
            "tipo": "restaurante",
            "municipio": municipio,
            "categoria": "",
            "tipo_comida": tipo_comida,
            "costo_estimado": costo,
            "tiempo_horas": 1,
            "nivel_afluencia": afluencia,
        })
        id_actual += 1

    return registros


# ─── Generacion de 200,000 transacciones para Apriori ────────────────────────

CATEGORIAS = ["naturaleza", "cultura", "gastronomia", "aventura",
              "familiar", "descanso", "fotografia", "eventos"]

PESO_INTERES_PRIMARIO = {
    "naturaleza":  0.20, "cultura":     0.18, "gastronomia": 0.14,
    "aventura":    0.15, "familiar":    0.12, "descanso":    0.08,
    "fotografia":  0.07, "eventos":     0.06,
}

PROB_COMPLEMENTARIA = {
    "naturaleza":  {"aventura": 0.45, "fotografia": 0.38, "gastronomia": 0.22, "descanso": 0.12},
    "cultura":     {"gastronomia": 0.55, "fotografia": 0.42, "eventos": 0.20, "naturaleza": 0.15},
    "gastronomia": {"cultura": 0.40, "eventos": 0.32, "familiar": 0.25, "naturaleza": 0.18},
    "aventura":    {"fotografia": 0.52, "naturaleza": 0.48, "descanso": 0.20, "gastronomia": 0.15},
    "familiar":    {"descanso": 0.50, "gastronomia": 0.30, "naturaleza": 0.25, "eventos": 0.18},
    "descanso":    {"familiar": 0.55, "naturaleza": 0.30, "gastronomia": 0.20, "fotografia": 0.12},
    "fotografia":  {"cultura": 0.45, "naturaleza": 0.40, "aventura": 0.30, "gastronomia": 0.15},
    "eventos":     {"gastronomia": 0.60, "cultura": 0.35, "familiar": 0.25, "fotografia": 0.15},
}

TOTAL_TRANSACCIONES = 200_000


def generar_transaccion():
    cats = list(PESO_INTERES_PRIMARIO.keys())
    pesos = list(PESO_INTERES_PRIMARIO.values())
    primaria = random.choices(cats, weights=pesos, k=1)[0]
    visitas = {primaria}
    for cat, prob in PROB_COMPLEMENTARIA.get(primaria, {}).items():
        if random.random() < prob:
            visitas.add(cat)
    return sorted(visitas)


def generar_historial():
    return [generar_transaccion() for _ in range(TOTAL_TRANSACCIONES)]


# ─── Escritura de archivos ────────────────────────────────────────────────────

CAMPOS = ["id", "nombre", "tipo", "municipio", "categoria",
          "tipo_comida", "costo_estimado", "tiempo_horas", "nivel_afluencia"]


def guardar_destinos_csv(destinos, restaurantes):
    ruta = DATA_DIR / "destinos.csv"
    todos = destinos + restaurantes
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CAMPOS)
        writer.writeheader()
        writer.writerows(todos)
    print(f"destinos.csv: {len(destinos)} destinos + {len(restaurantes)} restaurantes = {len(todos)} total")


def guardar_historial_csv(transacciones):
    ruta = DATA_DIR / "historial_visitas.csv"
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["categorias"])
        for t in transacciones:
            writer.writerow(["|".join(t)])
    print(f"historial_visitas.csv: {len(transacciones):,} transacciones")


if __name__ == "__main__":
    print("Generando 200,000 destinos...")
    destinos, siguiente_id = generar_destinos()

    print("Generando 200,000 restaurantes...")
    restaurantes = generar_restaurantes(siguiente_id)

    guardar_destinos_csv(destinos, restaurantes)

    print("Generando 200,000 transacciones para Apriori...")
    transacciones = generar_historial()
    guardar_historial_csv(transacciones)

    print("Listo.")
