"""Base service error class and FastAPI exception handler.

Service-layer errors carry a user-safe message and an HTTP status code. A
single handler registered on the FastAPI app maps any ServiceError subclass
to a JSONResponse, removing the need for try/except boilerplate in routes.
"""

from fastapi import Request
from fastapi.responses import JSONResponse


class ServiceError(Exception):
    """Base class for service-layer errors that map to HTTP responses."""

    status_code: int = 400

    def __init__(self, message: str, status_code: int | None = None):
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        super().__init__(message)


class CharacterServiceError(ServiceError):
    """Character service error with a user-safe message.

    Shared across `character_service`, `character_io`, and the other
    character-domain modules so raising from low-level helpers doesn't
    create circular imports.
    """

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message, status_code=status_code)


class CreatureServiceError(ServiceError):
    """Creature catalog service error with a user-safe message.

    Mirrors `CharacterServiceError` for the creature domain so raises from
    `creature_service`, `creature_io`, and `creature_parser` don't have to
    reuse the character error class.
    """

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message, status_code=status_code)


async def service_error_handler(_request: Request, exc: ServiceError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
    )
