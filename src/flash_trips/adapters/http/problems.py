from uuid import UUID

from fastapi import Request
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


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = str(uuid7())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = str(request_id)
        return response


async def http_problem(request: Request, error: Exception) -> JSONResponse:
    if not isinstance(error, HTTPException):
        raise error

    if error.status_code == 404:
        problem = Problem(
            type="https://flash-trips.example/problems/route-not-found",
            title="Not Found",
            status=404,
            detail="The requested resource was not found.",
            code="route_not_found",
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

    return problem_json(problem)


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


def problem_json(problem: Problem) -> JSONResponse:
    request_id = str(problem.request_id)
    return JSONResponse(
        ProblemResponse.model_validate(problem, from_attributes=True).model_dump(
            mode="json"
        ),
        status_code=problem.status,
        media_type="application/problem+json",
        headers={"X-Request-ID": request_id},
    )
