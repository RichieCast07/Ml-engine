import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ["REQUIRE_INTERNAL_AUTH"] = "false"
os.environ["ENABLE_DOCS"] = "true"

# Importar modelos antes de create_all para registrar InferenciaLog en Base.metadata.
from app.database import Base, get_db
import app.models  # noqa: F401
from app.main import app

# StaticPool: todas las conexiones comparten la misma DB en memoria.
engine_test = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)

Base.metadata.create_all(bind=engine_test)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
def client():
    return TestClient(app)
