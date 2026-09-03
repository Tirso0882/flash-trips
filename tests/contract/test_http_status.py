from typing import Any, NoReturn, cast
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from flash_trips.composition import create_app


@pytest.mark.asyncio
async def test_service_status_is_available_through_versioned_http() -> None:
    transport = ASGITransport(app=create_app())

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/status")

    assert response.status_code == 200
    assert response.json() == {
        "api_version": "v1",
        "service": "flash-trips-api",
        "status": "ok",
    }
    assert response.headers["content-type"] == "application/json"


@pytest.mark.asyncio
async def test_unknown_route_returns_a_typed_problem() -> None:
    transport = ASGITransport(app=create_app())

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/not-a-route")

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    problem = response.json()
    request_id = problem.pop("request_id")
    assert UUID(request_id).version == 7
    assert response.headers["x-request-id"] == request_id
    assert problem == {
        "code": "route_not_found",
        "detail": "The requested resource was not found.",
        "retryable": False,
        "status": 404,
        "title": "Not Found",
        "type": "https://flash-trips.example/problems/route-not-found",
    }


@pytest.mark.asyncio
async def test_unexpected_error_returns_a_safe_typed_problem() -> None:
    app = create_app()

    def fail_safely() -> NoReturn:
        raise RuntimeError("private database detail")

    app.add_api_route("/api/v1/failure-test", fail_safely, response_model=None)
    transport = ASGITransport(app=app, raise_app_exceptions=False)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/failure-test")

    problem = cast(dict[str, Any], response.json())
    assert response.status_code == 500
    assert response.headers["content-type"] == "application/problem+json"
    assert UUID(cast(str, problem["request_id"])).version == 7
    assert "private database detail" not in response.text
