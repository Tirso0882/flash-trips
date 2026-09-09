from collections.abc import Mapping
from typing import cast
from uuid import UUID

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict
from starlette.exceptions import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

from flash_trips.kernel.identifiers import uuid7
from flash_trips.kernel.problem import Problem


class ProblemResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: str
    title: str
    status: int
    detail: str
    code: str
    retryable: bool
    request_id: UUID
    run_id: UUID | None = None


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = str(uuid7())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = str(request_id)
        return response


def _active_run_reference(detail: object) -> UUID | None:
    if not isinstance(detail, Mapping):
        return None
    # HTTPException.detail has an untyped framework shape; keys are checked below.
    fields = cast(Mapping[str, object], detail)
    run_id = fields.get("run_id")
    if fields.get("code") != "active_run_exists" or not isinstance(run_id, str):
        return None
    return UUID(run_id)


async def http_problem(request: Request, error: Exception) -> JSONResponse:
    if not isinstance(error, HTTPException):
        raise error
    active_run_id = _active_run_reference(error.detail)

    if error.status_code == 401:
        problem = Problem(
            type="https://flash-trips.example/problems/authentication-required",
            title="Unauthorized",
            status=401,
            detail="Authentication is required.",
            code="authentication_required",
            retryable=False,
            request_id=request.state.request_id,
        )
    elif error.status_code == 403:
        problem = Problem(
            type="https://flash-trips.example/problems/access-denied",
            title="Forbidden",
            status=403,
            detail="Access is denied.",
            code="access_denied",
            retryable=False,
            request_id=request.state.request_id,
        )
    elif error.status_code == 404 and error.detail == "trip_not_found":
        problem = Problem(
            type="https://flash-trips.example/problems/trip-not-found",
            title="Not Found",
            status=404,
            detail="The Trip was not found.",
            code="trip_not_found",
            retryable=False,
            request_id=request.state.request_id,
        )
    elif error.status_code == 404 and error.detail == "run_not_found":
        problem = Problem(
            type="https://flash-trips.example/problems/run-not-found",
            title="Not Found",
            status=404,
            detail="The Run was not found.",
            code="run_not_found",
            retryable=False,
            request_id=request.state.request_id,
        )
    elif error.status_code == 409 and active_run_id is not None:
        problem = Problem(
            type="https://flash-trips.example/problems/active-run-exists",
            title="Active Run Exists",
            status=409,
            detail="An active mutating Run already exists for this Trip.",
            code="active_run_exists",
            retryable=False,
            request_id=request.state.request_id,
            run_id=active_run_id,
        )
    elif error.status_code == 404:
        problem = Problem(
            type="https://flash-trips.example/problems/route-not-found",
            title="Not Found",
            status=404,
            detail="The requested resource was not found.",
            code="route_not_found",
            retryable=False,
            request_id=request.state.request_id,
        )
    elif error.status_code == 422 and error.detail == "unsupported_structure":
        problem = Problem(
            type="https://flash-trips.example/problems/unsupported-trip-structure",
            title="Unsupported Trip Structure",
            status=422,
            detail="The current release supports exactly one city stay.",
            code="unsupported_structure",
            retryable=False,
            request_id=request.state.request_id,
        )
    else:
        problem = Problem(
            type="https://flash-trips.example/problems/http-error",
            title="Request Failed",
            status=error.status_code,
            detail="The request could not be completed.",
            code="http_error",
            retryable=False,
            request_id=request.state.request_id,
        )

    return problem_json(problem, headers=error.headers)


async def validation_problem(
    request: Request,
    error: Exception,
) -> JSONResponse:
    if not isinstance(error, RequestValidationError):
        raise error
    return problem_json(
        Problem(
            type="https://flash-trips.example/problems/invalid-request",
            title="Invalid Request",
            status=422,
            detail="The request did not match the required contract.",
            code="invalid_request",
            retryable=False,
            request_id=request.state.request_id,
        )
    )


async def unhandled_problem(request: Request, error: Exception) -> JSONResponse:
    del error
    return problem_json(
        Problem(
            type="https://flash-trips.example/problems/internal-error",
            title="Internal Server Error",
            status=500,
            detail="The request could not be completed.",
            code="internal_error",
            retryable=True,
            request_id=request.state.request_id,
        )
    )


def problem_json(
    problem: Problem,
    *,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    request_id = str(problem.request_id)
    response_headers = dict(headers or {})
    response_headers["X-Request-ID"] = request_id
    return JSONResponse(
        ProblemResponse.model_validate(problem, from_attributes=True).model_dump(
            mode="json",
            exclude_none=True,
        ),
        status_code=problem.status,
        media_type="application/problem+json",
        headers=response_headers,
    )
