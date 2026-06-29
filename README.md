# ExploraChiapas — Motor ML (Capa 2)

Microservicio de mineria de datos no supervisada que recibe los parametros de
viaje ya estructurados (la salida de la Capa 1 / servicio NLP) y devuelve un
itinerario concreto basado solo en datos reales del catalogo, sin que el LLM
pueda inventar lugares.

Implementa las 4 tecnicas descritas en la arquitectura del proyecto:

1. **Filtrado y scoring** — descarta destinos/restaurantes que no calzan con
   categoria, ubicacion, comida, presupuesto o tiempo.
2. **Clustering K-Means** (`app/clustering.py`) — agrupa los destinos por
   nivel de afluencia y costo en 3 clusters (`saturado`, `moderado`,
   `potencial_oculto`), etiquetados automaticamente por afluencia promedio.
3. **Reglas de asociacion Apriori** (`app/asociacion.py`) — sobre un
   historial sintetico de categorias co-visitadas, sugiere intereses
   complementarios al solicitado (ej. `aventura -> fotografia`).
4. **Optimizacion de mochila** (`app/knapsack.py`) — DP 0/1 en dos
   dimensiones (presupuesto y tiempo) que selecciona el subconjunto de
   actividades de mayor valor sin exceder ninguna restriccion. El "valor" de
   cada actividad se ajusta con bonus si coincide con el interes principal,
   si es una categoria complementaria (Apriori), o si pertenece al cluster
   `potencial_oculto` (para fomentar turismo sostenible).

## Setup

```bash
python -m venv venv
.\venv\Scripts\activate          # Windows
pip install -r requirements.txt

# (opcional) regenerar el historial sintetico de visitas para Apriori
python scripts/generar_historial_sintetico.py

uvicorn app.main:app --reload --port 8001
```

Swagger / OpenAPI: `http://localhost:8001/docs`

## Endpoints

- `GET /health`
- `POST /recomendar` — recibe `{destino, interes, comida, personas, presupuesto, tiempo}`
  (misma forma que la salida del servicio NLP de Capa 1) y devuelve el
  itinerario, costo y tiempo totales, reglas de asociacion aplicadas y un
  resumen de clusters entre los candidatos filtrados. Cada llamada se
  persiste en SQLite (`ml_engine.db`).
- `GET /historial?limite=20` — lista las ultimas inferencias guardadas.
- `GET /historial/{id}` — detalle de una inferencia especifica.

## Sobre los datos

- `data/destinos.json`: catalogo semilla de 34 destinos reales de Chiapas (4
  por cada una de las 8 categorias de interes) + 8 restaurantes, con costo,
  duracion y un nivel de afluencia estimado de forma ilustrativa. **Debe
  sustituirse** por datos reales (Secretaria de Turismo de Chiapas, DENUE)
  cuando el equipo los tenga etiquetados.
- `data/historial_visitas.json`: transacciones sinteticas de categorias
  co-visitadas, generadas con semilla fija (`scripts/generar_historial_sintetico.py`)
  para que Apriori tenga algo sobre lo cual entrenar mientras la app no
  tiene usuarios reales. Sustituir por el historial real de itinerarios en
  cuanto exista.

## Evidencia de desarrollo

`notebooks/entrenamiento_y_evaluacion.ipynb` documenta el entrenamiento y
evaluacion de K-Means (metodo del codo + silhouette para justificar
`k=3`, silhouette final 0.513) y Apriori (reglas descubiertas con su
soporte/confianza), ademas de un ejemplo end-to-end real usando
`generar_recomendacion()`. Importa directamente los modulos de `app/`, asi
que los resultados son los mismos que devuelve la API, no una reimplementacion
aparte.

Para volver a ejecutarlo:

```bash
pip install -r requirements-dev.txt
python -m ipykernel install --user --name explorachiapas-ml --display-name "ExploraChiapas ML"
jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.kernel_name=explorachiapas-ml notebooks/entrenamiento_y_evaluacion.ipynb
```

O abrirlo interactivamente con `jupyter lab` / `jupyter notebook` y correrlo celda por celda.

## Notas de diseño

- El cluster `potencial_oculto` recibe un bonus de score y el `saturado` una
  penalizacion, para que el knapsack tienda a recomendar destinos menos
  saturados cuando hay varias opciones equivalentes — esto conecta
  directamente con el objetivo de turismo sostenible del proyecto.
- `horas_desde_texto()` en `app/recomendador.py` es una heuristica simple
  (no un modelo) para convertir frases como "medio dia" o "2 dias" a horas
  numericas; se documenta como limitacion conocida.
