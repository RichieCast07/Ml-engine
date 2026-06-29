from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class InferenciaLog(Base):
    __tablename__ = "inferencias"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parametros_entrada: Mapped[dict] = mapped_column(JSON)
    resultado: Mapped[dict] = mapped_column(JSON)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
