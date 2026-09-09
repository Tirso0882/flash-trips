from collections.abc import AsyncIterator
from dataclasses import dataclass

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from flash_trips.composition import create_app
from flash_trips.kernel.authenticated_principal import AuthenticatedPrincipal
from tests.contract.test_http_run import (
    OTHER_PLANNER_ID,
    PLANNER_ID,
    FakePlannerResolver,
    MemoryUnitOfWorkFactory,
)


@dataclass(frozen=True, slots=True)
class SecurityAccessTokenVerifier:
    def verify(self, access_token: str) -> AuthenticatedPrincipal:
        if access_token == "operator-token":  # noqa: S105 - synthetic test token
            return AuthenticatedPrincipal(
                issuer="https://issuer.example",
                subject="operator-only",
                scopes=frozenset({"operator:read"}),
            )
        planner = OTHER_PLANNER_ID if access_token.endswith("other") else PLANNER_ID
        return AuthenticatedPrincipal(
            issuer="https://issuer.example",
            subject=str(planner),
            scopes=frozenset({"principal:read"}),
        )


@dataclass(frozen=True, slots=True)
class TwoPlannerFixture:
    client: AsyncClient
    store: MemoryUnitOfWorkFactory
    owner_headers: dict[str, str]
    other_headers: dict[str, str]
    operator_headers: dict[str, str]


@pytest_asyncio.fixture
async def two_planners() -> AsyncIterator[TwoPlannerFixture]:
    store = MemoryUnitOfWorkFactory()
    async with AsyncClient(
        transport=ASGITransport(
            app=create_app(
                access_token_verifier=SecurityAccessTokenVerifier(),
                planner_resolver=FakePlannerResolver(),
                unit_of_work_factory=store,
            )
        ),
        base_url="http://test",
        headers={"Authorization": "Bearer owner-token"},
    ) as client:
        yield TwoPlannerFixture(
            client=client,
            store=store,
            owner_headers={"Authorization": "Bearer owner-token"},
            other_headers={"Authorization": "Bearer planner-other"},
            operator_headers={"Authorization": "Bearer operator-token"},
        )
