"""Domain errors and failures upstream, as HTTP answers."""

import logfire
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from core import error_response
from domain.errors import DomainError


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def domain_error(request: Request, exc: DomainError):
        return JSONResponse(status_code=exc.status, content={"detail": exc.detail})

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        status, detail = error_response(exc)
        log = logfire.exception if status == 500 else logfire.warning
        log("Request failed with {status} on {method} {path}", status=status, method=request.method, path=request.url.path, _exc_info=exc)
        return JSONResponse(status_code=status, content={"detail": detail})
