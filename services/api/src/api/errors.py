from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ProblemDetails(BaseModel):
    type: str = "about:blank"
    title: str
    status: int
    detail: str
    instance: str | None = None


class ProblemException(Exception):
    def __init__(
        self,
        status_code: int,
        title: str,
        detail: str,
        type_uri: str = "about:blank",
    ) -> None:
        self.status_code = status_code
        self.title = title
        self.detail = detail
        self.type_uri = type_uri
        super().__init__(detail)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ProblemException)
    async def problem_exception_handler(request: Request, exc: ProblemException) -> JSONResponse:
        problem = ProblemDetails(
            type=exc.type_uri,
            title=exc.title,
            status=exc.status_code,
            detail=exc.detail,
            instance=request.url.path,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=problem.model_dump(),
            media_type="application/problem+json",
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        title_map = {
            400: "Bad Request",
            401: "Unauthorized",
            403: "Forbidden",
            404: "Not Found",
            409: "Conflict",
            422: "Unprocessable Entity",
            429: "Too Many Requests",
            500: "Internal Server Error",
        }
        title = title_map.get(exc.status_code, "HTTP Error")
        problem = ProblemDetails(
            type=f"https://api.vigil.dev/errors/{title.lower().replace(' ', '-')}",
            title=title,
            status=exc.status_code,
            detail=str(exc.detail),
            instance=request.url.path,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=problem.model_dump(),
            media_type="application/problem+json",
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        problem = ProblemDetails(
            type="https://api.vigil.dev/errors/validation-error",
            title="Unprocessable Entity",
            status=422,
            detail=str(exc.errors()),
            instance=request.url.path,
        )
        return JSONResponse(
            status_code=422,
            content=problem.model_dump(),
            media_type="application/problem+json",
        )
