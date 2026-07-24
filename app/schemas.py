from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

CategoriaInteres = Literal[
    "naturaleza", "cultura", "gastronomia", "aventura",
    "familiar", "descanso", "fotografia", "eventos",
]

_CATEGORIAS_VALIDAS: set[str] = {
    "naturaleza", "cultura", "gastronomia", "aventura",
    "familiar", "descanso", "fotografia", "eventos",
}


class ParametrosViajeIn(BaseModel):
    """Misma forma que la salida de la Capa 1 (servicio NLP)."""

    destino: Optional[str] = None

    # interes: campo legacy (una sola categoría). Se mantiene para retrocompat.
    # Si se envían ambos, `intereses` tiene prioridad y `interes` se ignora.
    interes: Optional[CategoriaInteres] = None

    # intereses: hasta 3 categorías que le gustan al usuario.
    intereses: list[CategoriaInteres] = Field(default_factory=list)

    # categorias_excluidas: filtro duro — nunca aparecen en el resultado,
    # ni siquiera en los fallbacks. El usuario declaró no querer estas categorías.
    categorias_excluidas: list[CategoriaInteres] = Field(default_factory=list)

    comida: Optional[str] = None
    personas: Optional[int] = Field(default=1, ge=1, le=50)
    presupuesto: Optional[float] = Field(default=None, ge=0)
    tiempo: Optional[str] = None

    @model_validator(mode="after")
    def unificar_intereses(self) -> "ParametrosViajeIn":
        # Si solo viene `interes` (retrocompat), lo promovemos a `intereses`.
        if self.interes and not self.intereses:
            self.intereses = [self.interes]
        # Si `intereses` está poblado, fijamos `interes` al primero para que
        # el código legacy que lo lea siga funcionando.
        if self.intereses and not self.interes:
            self.interes = self.intereses[0]
        # Nunca puede haber una categoría en intereses Y en excluidas al mismo tiempo.
        excluidas = set(self.categorias_excluidas)
        self.intereses = [i for i in self.intereses if i not in excluidas]
        if self.interes and self.interes in excluidas:
            self.interes = None
        return self

    @property
    def set_intereses(self) -> set[str]:
        """Conjunto unificado de todas las categorías deseadas."""
        return set(self.intereses)


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
    foto_principal: Optional[str] = None


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
    mensaje: Optional[str] = None
    es_fallback: bool = False
    creado_en: datetime

    model_config = ConfigDict(from_attributes=True)
