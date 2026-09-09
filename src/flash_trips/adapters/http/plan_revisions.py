from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Security
from pydantic import BaseModel, ConfigDict

from flash_trips.adapters.http.principal import authenticated_planner
from flash_trips.adapters.http.problems import ProblemResponse
from flash_trips.application import (
    AccessTokenVerifier,
    PlanClaimKind,
    PlannerPrincipal,
    PlannerResolver,
    PlanRevisionRecord,
    TripPlanning,
)

# SKELETON_REPLACEMENT: issue 216 (FT-14) deepens this thin Plan Revision HTTP station.


class PlanClaimResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    kind: PlanClaimKind
    text: str
    evidence_reference: str
    observed_at: datetime


class PlanRevisionResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    trip_id: UUID
    run_id: UUID
    revision_number: int
    base_revision_id: UUID | None
    claims: tuple[PlanClaimResponse, ...]


def _response(revision: PlanRevisionRecord) -> PlanRevisionResponse:
    return PlanRevisionResponse(
        id=revision.id,
        trip_id=revision.trip_id,
        run_id=revision.run_id,
        revision_number=revision.revision_number,
        base_revision_id=revision.base_revision_id,
        claims=tuple(
            PlanClaimResponse(
                id=claim.id,
                kind=claim.kind,
                text=claim.text,
                evidence_reference=claim.evidence_reference.value,
                observed_at=claim.observed_at,
            )
            for claim in revision.claims
        ),
    )


def plan_revision_router(
    trip_planning: TripPlanning,
    access_token_verifier: AccessTokenVerifier,
    planner_resolver: PlannerResolver,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/trips")
    planner = authenticated_planner(access_token_verifier, planner_resolver)

    async def get_current_plan_revision(
        trip_id: UUID,
        principal: Annotated[PlannerPrincipal, Security(planner)],
    ) -> PlanRevisionResponse:
        revision = await trip_planning.get_current_plan_revision(principal, trip_id)
        if revision is None:
            raise HTTPException(status_code=404, detail="plan_revision_not_found")
        return _response(revision)

    # FastAPI's open-ended response metadata requires Any at this framework seam.
    responses: dict[int | str, dict[str, Any]] = {
        status: {
            "description": description,
            "model": ProblemResponse,
            "content": {"application/problem+json": {}},
        }
        for status, description in (
            (401, "Unauthorized"),
            (403, "Forbidden"),
            (404, "Plan Revision Not Found"),
            (422, "Unprocessable Request"),
        )
    }
    router.add_api_route(
        "/{trip_id}/plan-revision",
        get_current_plan_revision,
        methods=["GET"],
        response_model=PlanRevisionResponse,
        operation_id="getCurrentPlanRevision",
        responses=responses,
    )
    return router
