import os

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import verificar_clave_interna
from app.database import Base, engine, get_db
from app.models import InferenciaLog
from app.recomendador import generar_recomendacion
from app.schemas import ParametrosViajeIn, RecomendacionOut

Base.metadata.create_all(bind=engine)

# Desactivar /docs y /openapi.json en producción para no exponer el contrato interno.
_ENABLE_DOCS = os.environ.get("ENABLE_DOCS", "true").lower() == "true"

app = FastAPI(
    title="ExploraChiapas - Motor ML (Capa 2)",
    description=(
        "Microservicio de mineria de datos no supervisada: clustering K-Means "
        "de destinos por afluencia, reglas de asociacion Apriori sobre "
        "categorias co-visitadas y optimizacion de mochila para armar el "
        "itinerario final dentro del presupuesto y tiempo del turista."
    ),
    version="0.1.0",
    docs_url="/docs" if _ENABLE_DOCS else None,
    redoc_url="/redoc" if _ENABLE_DOCS else None,
    openapi_url="/openapi.json" if _ENABLE_DOCS else None,
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post(
    "/recomendar",
    response_model=RecomendacionOut,
    dependencies=[Depends(verificar_clave_interna)],
)
def recomendar(params: ParametrosViajeIn, db: Session = Depends(get_db)):
    try:
        resultado = generar_recomendacion(params)
    except Exception:
        raise HTTPException(status_code=500, detail="Error al generar la recomendación")

    resultado_sin_params = {k: v for k, v in resultado.items() if k != "parametros_entrada"}

    log = InferenciaLog(
        parametros_entrada=params.model_dump(mode="json"),
        resultado=resultado_sin_params,
    )
    db.add(log)
    db.commit()
    db.refresh(log)

    return RecomendacionOut(id=log.id, creado_en=log.creado_en, **resultado)


@app.get(
    "/historial",
    response_model=list[RecomendacionOut],
    dependencies=[Depends(verificar_clave_interna)],
)
def listar_historial(
    limite: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    registros = (
        db.query(InferenciaLog).order_by(InferenciaLog.id.desc()).limit(limite).all()
    )
    return [
        RecomendacionOut(
            id=r.id,
            creado_en=r.creado_en,
            parametros_entrada=r.parametros_entrada,
            **r.resultado,
        )
        for r in registros
    ]


@app.get(
    "/historial/{inferencia_id}",
    response_model=RecomendacionOut,
    dependencies=[Depends(verificar_clave_interna)],
)
def obtener_inferencia(inferencia_id: int, db: Session = Depends(get_db)):
    registro = db.query(InferenciaLog).filter(InferenciaLog.id == inferencia_id).first()
    if registro is None:
        raise HTTPException(status_code=404, detail="Inferencia no encontrada")

    return RecomendacionOut(
        id=registro.id,
        creado_en=registro.creado_en,
        parametros_entrada=registro.parametros_entrada,
        **registro.resultado,
    )
