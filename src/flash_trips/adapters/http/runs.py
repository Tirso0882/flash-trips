from enum import StrEnum
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, Security
from pydantic import BaseModel, ConfigDict

from flash_trips.adapters.http.principal import authenticated_planner
from flash_trips.adapters.http.problems import ProblemResponse
from flash_trips.application import (
    AccessTokenVerifier,
    ActiveRunExistsError,
    PlannerPrincipal,
    PlannerResolver,
    RunRecord,
    RunTerminalStatus,
    TripNotFoundError,
    TripPlanning,
)


class RunStatus(StrEnum):
    RUNNING = "Running"
    SUCCEEDED = RunTerminalStatus.SUCCEEDED.value
    BLOCKED = RunTerminalStatus.BLOCKED.value
    FAILED = RunTerminalStatus.FAILED.value
    CANCELLED = RunTerminalStatus.CANCELLED.value


class RunTerminalOutcomeResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: RunTerminalStatus
    code: str
    detail: str


class RunResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    trip_id: UUID
    status: RunStatus
    terminal_outcome: RunTerminalOutcomeResponse | None


def _response(run: RunRecord) -> RunResponse:
    outcome = run.terminal_outcome
    if outcome is None:
        return RunResponse(
            id=run.id,
            trip_id=run.trip_id,
            status=RunStatus.RUNNING,
            terminal_outcome=None,
        )
    return RunResponse(
        id=run.id,
        trip_id=run.trip_id,
        status=RunStatus(outcome.status.value),
        terminal_outcome=RunTerminalOutcomeResponse(
            status=outcome.status,
            code=outcome.code,
            detail=outcome.detail,
        ),
    )


def _problem_responses(
    *statuses: int,
) -> dict[int | str, dict[str, Any]]:
    # FastAPI owns this heterogeneous response-metadata shape.
    descriptions = {
        401: "Unauthorized",
        403: "Forbidden",
        404: "Not Found",
        409: "Conflict",
        422: "Unprocessable Request",
    }
    return {
        status: {
            "description": descriptions[status],
            "model": ProblemResponse,
            "content": {"application/problem+json": {}},
        }
        for status in statuses
    }


def run_router(
    trip_planning: TripPlanning,
    access_token_verifier: AccessTokenVerifier,
    planner_resolver: PlannerResolver,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1")
    planner = authenticated_planner(access_token_verifier, planner_resolver)

    async def start_run(
        trip_id: UUID,
        response: Response,
        principal: Annotated[PlannerPrincipal, Security(planner)],
    ) -> RunResponse:
        try:
            run = await trip_planning.start_run(principal, trip_id)
        except TripNotFoundError:
            raise HTTPException(status_code=404, detail="trip_not_found") from None
        except ActiveRunExistsError as error:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "active_run_exists",
                    "run_id": str(error.active_run_id),
                },
            ) from None
        response.headers["Location"] = f"/api/v1/runs/{run.id}"
        return _response(run)

    async def get_run(
        run_id: UUID,
        principal: Annotated[PlannerPrincipal, Security(planner)],
    ) -> RunResponse:
        run = await trip_planning.get_run(principal, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="run_not_found")
        return _response(run)

    router.add_api_route(
        "/trips/{trip_id}/runs",
        start_run,
        methods=["POST"],
        response_model=RunResponse,
        status_code=202,
        operation_id="startRun",
        responses=_problem_responses(401, 403, 404, 409, 422),
    )
    router.add_api_route(
        "/runs/{run_id}",
        get_run,
        methods=["GET"],
        response_model=RunResponse,
        operation_id="getRun",
        responses=_problem_responses(401, 403, 404, 422),
    )
    return router
