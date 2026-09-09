from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Security, status
from pydantic import BaseModel, ConfigDict

from flash_trips.adapters.http.principal import authenticated_planner
from flash_trips.adapters.http.problems import ProblemResponse
from flash_trips.application import (
    AccessTokenVerifier,
    ApprovalAlreadyRecordedError,
    ApprovalNotFoundError,
    ApprovalRecord,
    ApprovalRequestRecord,
    BoundApprovalAction,
    PlannerPrincipal,
    PlannerResolver,
    TripPlanning,
)


class BoundApprovalActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    approval_request_id: UUID
    plan_revision_id: UUID


class ApprovalRequestResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    plan_revision_id: UUID
    approval_id: UUID | None


class ApprovalResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    approval_request_id: UUID
    plan_revision_id: UUID


def _approval_response(approval: ApprovalRecord) -> ApprovalResponse:
    return ApprovalResponse(
        id=approval.id,
        approval_request_id=approval.approval_request_id,
        plan_revision_id=approval.plan_revision_id,
    )


def _problem_responses() -> dict[int | str, dict[str, Any]]:
    return {
        problem_status: {
            "description": description,
            "model": ProblemResponse,
            "content": {"application/problem+json": {}},
        }
        for problem_status, description in (
            (401, "Unauthorized"),
            (403, "Forbidden"),
            (404, "Approval Not Found"),
            (409, "Approval Already Recorded"),
            (422, "Unprocessable Request"),
        )
    }


def approval_router(
    trip_planning: TripPlanning,
    access_token_verifier: AccessTokenVerifier,
    planner_resolver: PlannerResolver,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1")
    planner = authenticated_planner(access_token_verifier, planner_resolver)

    async def get_current_approval_request(
        trip_id: UUID,
        principal: Annotated[PlannerPrincipal, Security(planner)],
    ) -> ApprovalRequestResponse:
        request = await trip_planning.get_current_approval_request(principal, trip_id)
        if request is None:
            raise HTTPException(status_code=404, detail="approval_not_found")
        return await _request_response(trip_planning, principal, request)

    async def approve_plan_revision(
        body: BoundApprovalActionRequest,
        principal: Annotated[PlannerPrincipal, Security(planner)],
    ) -> ApprovalResponse:
        try:
            approval = await trip_planning.approve_plan_revision(
                principal,
                BoundApprovalAction(
                    approval_request_id=body.approval_request_id,
                    plan_revision_id=body.plan_revision_id,
                ),
            )
        except ApprovalNotFoundError as error:
            raise HTTPException(
                status_code=404,
                detail="approval_not_found",
            ) from error
        except ApprovalAlreadyRecordedError as error:
            raise HTTPException(
                status_code=409,
                detail="approval_already_recorded",
            ) from error
        return _approval_response(approval)

    router.add_api_route(
        "/trips/{trip_id}/approval-request",
        get_current_approval_request,
        methods=["GET"],
        response_model=ApprovalRequestResponse,
        operation_id="getCurrentApprovalRequest",
        responses=_problem_responses(),
    )
    router.add_api_route(
        "/approvals",
        approve_plan_revision,
        methods=["POST"],
        response_model=ApprovalResponse,
        operation_id="approvePlanRevision",
        responses=_problem_responses(),
        status_code=status.HTTP_201_CREATED,
    )
    return router


async def _request_response(
    trip_planning: TripPlanning,
    principal: PlannerPrincipal,
    request: ApprovalRequestRecord,
) -> ApprovalRequestResponse:
    approval = await trip_planning.get_approval_for_plan_revision(
        principal,
        request.plan_revision_id,
    )
    return ApprovalRequestResponse(
        id=request.id,
        plan_revision_id=request.plan_revision_id,
        approval_id=approval.id if approval is not None else None,
    )
