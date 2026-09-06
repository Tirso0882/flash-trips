from fastapi import FastAPI
from starlette.exceptions import HTTPException

from flash_trips.adapters.http.openapi import install_problem_media_type
from flash_trips.adapters.http.problems import (
    ProblemResponse,
    RequestIdMiddleware,
    http_problem,
    unhandled_problem,
)
from flash_trips.adapters.http.status import status_router
from flash_trips.adapters.service_status import StaticServiceStatus
from flash_trips.adapters.telemetry import configure_logging
from flash_trips.application import TripPlanning


def create_app() -> FastAPI:
    app = FastAPI(
        title="Flash Trips API",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
        responses={
            404: {
                "description": "Not Found",
                "model": ProblemResponse,
                "content": {"application/problem+json": {}},
            },
            500: {
                "description": "Internal Server Error",
                "model": ProblemResponse,
                "content": {"application/problem+json": {}},
            },
        },
    )
    app.state.logger = configure_logging()
    app.add_middleware(RequestIdMiddleware)
    app.add_exception_handler(HTTPException, http_problem)
    app.add_exception_handler(Exception, unhandled_problem)
    app.include_router(status_router(TripPlanning(StaticServiceStatus())))
    install_problem_media_type(app)
    return app


__all__ = ["create_app"]
