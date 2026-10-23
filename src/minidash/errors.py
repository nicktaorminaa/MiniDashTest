"""Domain errors and their HTTP mapping."""

from fastapi import Request
from fastapi.responses import JSONResponse


class DomainError(Exception):
    """A business-rule failure with a stable machine-readable code."""

    def __init__(self, code: str, message: str, status_code: int = 422):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class NotFoundError(DomainError):
    def __init__(self, code: str, message: str):
        super().__init__(code, message, status_code=404)


async def domain_error_handler(_request: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )
