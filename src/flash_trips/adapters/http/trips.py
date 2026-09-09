from datetime import date
from typing import Annotated, Any, Self
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, Security
from pydantic import BaseModel, ConfigDict, Field, model_validator

from flash_trips.adapters.http.principal import authenticated_planner
from flash_trips.adapters.http.problems import ProblemResponse
from flash_trips.application import (
    AccessTokenVerifier,
    NewTripStay,
    PlannerPrincipal,
    PlannerResolver,
    TripPlanning,
    TripRecord,
    UnsupportedTripStructureError,
)

# SKELETON_REPLACEMENT: issue 204 (FT-03) deepens this thin Trip HTTP station.


class TripStayInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    city: str = Field(min_length=1, max_length=200)
    starts_on: date
    ends_on: date
    nights: int = Field(ge=0)

    @model_validator(mode="after")
    def dates_are_ordered(self) -> Self:
        if self.ends_on < self.starts_on:
            raise ValueError("ends_on must not be before starts_on")
        return self


class TripStructureInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    stays: tuple[TripStayInput, ...] = Field(min_length=1)


class CreateTripRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    structure: TripStructureInput


class TripStayResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    city: str
    starts_on: date
    ends_on: date
    nights: int


class TripStructureResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    stays: tuple[TripStayResponse, ...]


class TripResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    structure: TripStructureResponse


class TripListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: tuple[TripResponse, ...]


def _response(trip: TripRecord) -> TripResponse:
    return TripResponse(
        id=trip.id,
        structure=TripStructureResponse(
            stays=tuple(
                TripStayResponse(
                    id=stay.id,
                    city=stay.city,
                    starts_on=stay.starts_on,
                    ends_on=stay.ends_on,
                    nights=stay.nights,
                )
                for stay in trip.structure.stays
            )
        ),
    )


def _problem_responses(
    *statuses: int,
) -> dict[int | str, dict[str, Any]]:
    # FastAPI's open-ended response metadata requires Any at this framework seam.
    return {
        status: {
            "description": {
                401: "Unauthorized",
                403: "Forbidden",
                404: "Trip Not Found",
                422: "Unprocessable Request",
            }[status],
            "model": ProblemResponse,
            "content": {"application/problem+json": {}},
        }
        for status in statuses
    }


def trip_router(
    trip_planning: TripPlanning,
    access_token_verifier: AccessTokenVerifier,
    planner_resolver: PlannerResolver,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/trips")
    planner = authenticated_planner(access_token_verifier, planner_resolver)

    async def create_trip(
        request: CreateTripRequest,
        response: Response,
        principal: Annotated[PlannerPrincipal, Security(planner)],
    ) -> TripResponse:
        try:
            trip = await trip_planning.create_trip(
                principal,
                tuple(
                    NewTripStay(
                        city=stay.city,
                        starts_on=stay.starts_on,
                        ends_on=stay.ends_on,
                        nights=stay.nights,
                    )
                    for stay in request.structure.stays
                ),
            )
        except UnsupportedTripStructureError:
            raise HTTPException(
                status_code=422,
                detail="unsupported_structure",
            ) from None
        response.headers["Location"] = f"/api/v1/trips/{trip.id}"
        return _response(trip)

    async def list_trips(
        principal: Annotated[PlannerPrincipal, Security(planner)],
    ) -> TripListResponse:
        trips = await trip_planning.list_trips(principal)
        return TripListResponse(items=tuple(_response(trip) for trip in trips))

    async def get_trip(
        trip_id: UUID,
        principal: Annotated[PlannerPrincipal, Security(planner)],
    ) -> TripResponse:
        trip = await trip_planning.get_trip(principal, trip_id)
        if trip is None:
            raise HTTPException(status_code=404, detail="trip_not_found")
        return _response(trip)

    router.add_api_route(
        "",
        create_trip,
        methods=["POST"],
        response_model=TripResponse,
        status_code=201,
        operation_id="createTrip",
        responses=_problem_responses(401, 403, 422),
    )
    router.add_api_route(
        "",
        list_trips,
        methods=["GET"],
        response_model=TripListResponse,
        operation_id="listTrips",
        responses=_problem_responses(401, 403),
    )
    router.add_api_route(
        "/{trip_id}",
        get_trip,
        methods=["GET"],
        response_model=TripResponse,
        operation_id="getTrip",
        responses=_problem_responses(401, 403, 404, 422),
    )
    return router
