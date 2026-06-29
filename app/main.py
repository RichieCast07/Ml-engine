from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db
from app.models import InferenciaLog
from app.recomendador import generar_recomendacion
from app.schemas import ParametrosViajeIn, RecomendacionOut

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="ExploraChiapas - Motor ML (Capa 2)",
    description=(
        "Microservicio de mineria de datos no supervisada: clustering K-Means "
        "de destinos por afluencia, reglas de asociacion Apriori sobre "
        "categorias co-visitadas y optimizacion de mochila para armar el "
        "itinerario final dentro del presupuesto y tiempo del turista."
    ),
    version="0.1.0",
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/recomendar", response_model=RecomendacionOut)
def recomendar(params: ParametrosViajeIn, db: Session = Depends(get_db)):
    resultado = generar_recomendacion(params)
    resultado_sin_params = {k: v for k, v in resultado.items() if k != "parametros_entrada"}

    log = InferenciaLog(
        parametros_entrada=params.model_dump(mode="json"),
        resultado=resultado_sin_params,
    )
    db.add(log)
    db.commit()
    db.refresh(log)

    return RecomendacionOut(id=log.id, creado_en=log.creado_en, **resultado)


@app.get("/historial", response_model=list[RecomendacionOut])
def listar_historial(limite: int = 20, db: Session = Depends(get_db)):
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


@app.get("/historial/{inferencia_id}", response_model=RecomendacionOut)
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
