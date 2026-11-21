"""The FastAPI application: routers under /api/v1 and every error as a problem (RFC 9457)."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from splitpy_app.adapters.rest.dependencies import Services
from splitpy_app.adapters.rest.problems import (
    PROBLEM_CONTENT_TYPE,
    STATUS_BY_CLIENT_ERROR,
    Problem,
    problem_for,
    validation_problem,
)
from splitpy_app.adapters.rest.routers import insights, payments
from splitpy_core.domain.errors import DomainError

API_PREFIX = "/api/v1"


def create_app(services: Services) -> FastAPI:
    app = FastAPI(title="splitPy")
    app.state.services = services
    app.add_exception_handler(RequestValidationError, _validation_error)
    for error in (DomainError, *STATUS_BY_CLIENT_ERROR):
        app.add_exception_handler(error, _error)
    # Starlette answers with this one and then re-raises, so the server still logs the error.
    app.add_exception_handler(Exception, _error)
    app.include_router(payments.router, prefix=API_PREFIX)
    app.include_router(insights.router, prefix=API_PREFIX)
    return app


async def _validation_error(request: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, RequestValidationError)
    return _response(validation_problem(error.errors(), request.url.path))


async def _error(request: Request, error: Exception) -> JSONResponse:
    return _response(problem_for(error, request.url.path))


def _response(problem: Problem) -> JSONResponse:
    return JSONResponse(
        problem.to_dict(), status_code=problem.status, media_type=PROBLEM_CONTENT_TYPE
    )
