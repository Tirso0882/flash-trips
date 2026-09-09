from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, Security, status
from pydantic import BaseModel, ConfigDict

from flash_trips.adapters.http.principal import authenticated_planner
from flash_trips.adapters.http.problems import ProblemResponse
from flash_trips.application import (
    AccessTokenVerifier,
    HandbookExportFormat,
    HandbookNotEligibleError,
    HandbookNotFoundError,
    HandbookSnapshotRecord,
    PlannerPrincipal,
    PlannerResolver,
    TripPlanning,
)


class HandbookSnapshotResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    plan_revision_id: UUID
    approval_id: UUID
    format: HandbookExportFormat
    checksum: str


def _snapshot_response(
    snapshot: HandbookSnapshotRecord,
) -> HandbookSnapshotResponse:
    return HandbookSnapshotResponse(
        id=snapshot.id,
        plan_revision_id=snapshot.plan_revision_id,
        approval_id=snapshot.approval_id,
        format=HandbookExportFormat.HTML,
        checksum=snapshot.checksum,
    )


def _problem_responses() -> dict[int | str, dict[str, Any]]:
    # FastAPI's open-ended response metadata requires Any at this framework seam.
    return {
        problem_status: {
            "description": description,
            "model": ProblemResponse,
            "content": {"application/problem+json": {}},
        }
        for problem_status, description in (
            (401, "Unauthorized"),
            (403, "Forbidden"),
            (404, "Handbook Not Found"),
            (409, "Handbook Not Eligible"),
            (422, "Unprocessable Request"),
        )
    }


def handbook_router(
    trip_planning: TripPlanning,
    access_token_verifier: AccessTokenVerifier,
    planner_resolver: PlannerResolver,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1")
    planner = authenticated_planner(access_token_verifier, planner_resolver)

    async def compile_handbook(
        trip_id: UUID,
        principal: Annotated[PlannerPrincipal, Security(planner)],
    ) -> HandbookSnapshotResponse:
        try:
            snapshot = await trip_planning.compile_current_handbook(principal, trip_id)
        except HandbookNotEligibleError as error:
            raise HTTPException(
                status_code=409,
                detail="handbook_not_eligible",
            ) from error
        return _snapshot_response(snapshot)

    async def download_handbook(
        snapshot_id: UUID,
        principal: Annotated[PlannerPrincipal, Security(planner)],
    ) -> Response:
        try:
            snapshot = await trip_planning.download_handbook(principal, snapshot_id)
        except HandbookNotFoundError as error:
            raise HTTPException(
                status_code=404,
                detail="handbook_not_found",
            ) from error
        return Response(
            content=snapshot.export_bytes,
            media_type="text/html; charset=utf-8",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="flash-trips-{snapshot.id}.html"'
                ),
                "Digest": f"sha-256={snapshot.checksum}",
            },
        )

    router.add_api_route(
        "/trips/{trip_id}/handbook-snapshots",
        compile_handbook,
        methods=["POST"],
        operation_id="compileHandbook",
        response_model=HandbookSnapshotResponse,
        responses=_problem_responses(),
        status_code=status.HTTP_201_CREATED,
    )
    router.add_api_route(
        "/handbook-snapshots/{snapshot_id}/export",
        download_handbook,
        methods=["GET"],
        operation_id="downloadHandbook",
        responses={
            **_problem_responses(),
            200: {
                "description": "Handbook HTML export",
                "content": {
                    "text/html": {"schema": {"type": "string", "format": "binary"}}
                },
            },
        },
        response_class=Response,
    )
    return router


__all__ = ["handbook_router"]
