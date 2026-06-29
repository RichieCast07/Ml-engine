from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, JSON

from app.database import Base


class InferenciaLog(Base):
    __tablename__ = "inferencias"

    id = Column(Integer, primary_key=True, autoincrement=True)
    parametros_entrada = Column(JSON)
    resultado = Column(JSON)
    creado_en = Column(DateTime, default=lambda: datetime.now(timezone.utc))
