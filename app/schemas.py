from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

CategoriaInteres = Literal[
    "naturaleza", "cultura", "gastronomia", "aventura",
    "familiar", "descanso", "fotografia", "eventos",
]


class ParametrosViajeIn(BaseModel):
    """Misma forma que la salida de la Capa 1 (servicio NLP)."""

    destino: Optional[str] = None
    interes: Optional[CategoriaInteres] = None
    comida: Optional[str] = None
    personas: Optional[int] = Field(default=1, ge=1, le=50)
    presupuesto: Optional[float] = Field(default=None, ge=0)
    tiempo: Optional[str] = None


class ActividadOut(BaseModel):
    id: int
    nombre: str
    tipo: Literal["destino", "restaurante"]
    municipio: str
    categoria: Optional[str] = None
    costo_estimado: float
    costo_total_grupo: float
    tiempo_horas: float
    nivel_afluencia: int
    cluster_afluencia: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None


class RecomendacionOut(BaseModel):
    id: int
    parametros_entrada: ParametrosViajeIn
    itinerario: list[ActividadOut]
    costo_total: float
    tiempo_total_horas: float
    presupuesto_disponible: Optional[float]
    tiempo_disponible_horas: float
    reglas_asociacion_aplicadas: list[str]
    resumen_clusters_candidatos: dict[str, int]
    creado_en: datetime

    model_config = ConfigDict(from_attributes=True)
