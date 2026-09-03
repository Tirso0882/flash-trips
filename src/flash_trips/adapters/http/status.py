from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from flash_trips.application import TripPlanning


class ServiceStatusResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    api_version: Literal["v1"]
    service: Literal["flash-trips-api"]
    status: Literal["ok"]


def status_router(trip_planning: TripPlanning) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    def service_status() -> ServiceStatusResponse:
        return ServiceStatusResponse.model_validate(
            trip_planning.service_status(), from_attributes=True
        )

    router.add_api_route(
        "/status",
        service_status,
        methods=["GET"],
        response_model=ServiceStatusResponse,
        operation_id="getServiceStatus",
    )
    return router
