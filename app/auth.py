import hmac
import os

from fastapi import Header, HTTPException, status

# Si REQUIRE_INTERNAL_AUTH=true, todos los endpoints de la API exigen el header.
# Si no está configurado o es false, el middleware es transparente (modo desarrollo).
_REQUIRE_AUTH: bool = os.environ.get("REQUIRE_INTERNAL_AUTH", "false").lower() == "true"
_INTERNAL_API_KEY: str = os.environ.get("INTERNAL_API_KEY", "")


def verificar_clave_interna(
    x_internal_service_key: str | None = Header(default=None),
) -> None:
    """
    Dependencia FastAPI para autenticación inter-servicio.
    Si REQUIRE_INTERNAL_AUTH=true, la solicitud debe incluir el header
    X-Internal-Service-Key con el valor correcto.
    La comparación usa hmac.compare_digest para evitar timing attacks.
    """
    if not _REQUIRE_AUTH:
        return

    if not x_internal_service_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autorizado",
        )

    # hmac.compare_digest requiere strings o bytes del mismo tipo.
    try:
        claves_iguales = hmac.compare_digest(
            x_internal_service_key.encode(),
            _INTERNAL_API_KEY.encode(),
        )
    except Exception:
        claves_iguales = False

    if not claves_iguales:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autorizado",
        )
