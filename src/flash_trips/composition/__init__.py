from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException

from flash_trips.adapters.config import RuntimeSettings
from flash_trips.adapters.http.openapi import install_problem_media_type
from flash_trips.adapters.http.plan_revisions import plan_revision_router
from flash_trips.adapters.http.principal import principal_router
from flash_trips.adapters.http.problems import (
    ProblemResponse,
    RequestIdMiddleware,
    http_problem,
    unhandled_problem,
    validation_problem,
)
from flash_trips.adapters.http.runs import run_router
from flash_trips.adapters.http.status import status_router
from flash_trips.adapters.http.trips import trip_router
from flash_trips.adapters.identity import (
    JwtAccessTokenVerifier,
    RejectingAccessTokenVerifier,
)
from flash_trips.adapters.postgres import (
    PostgresDatabase,
    PostgresExternalIdentityRepositoryFactory,
    PostgresUnitOfWorkFactory,
)
from flash_trips.adapters.service_status import StaticServiceStatus
from flash_trips.adapters.telemetry import configure_logging
from flash_trips.application import (
    AccessTokenVerifier,
    AllowedExternalIdentity,
    PlannerResolver,
    RejectingPlannerResolver,
    ResolvePlanner,
    TripPlanning,
    UnitOfWorkFactory,
)
from flash_trips.capabilities.travel_readiness import (
    FixtureTravelReadinessCapability,
)


def create_app(
    access_token_verifier: AccessTokenVerifier | None = None,
    planner_resolver: PlannerResolver | None = None,
    database: PostgresDatabase | None = None,
    unit_of_work_factory: UnitOfWorkFactory | None = None,
) -> FastAPI:
    if access_token_verifier is None:
        access_token_verifier = RejectingAccessTokenVerifier()
    if planner_resolver is None:
        planner_resolver = RejectingPlannerResolver()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        del app
        try:
            yield
        finally:
            if database is not None:
                await database.close()

    app = FastAPI(
        title="Flash Trips API",
        version="1.0.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        responses={
            404: {
                "description": "Not Found",
                "model": ProblemResponse,
                "content": {"application/problem+json": {}},
            },
            500: {
                "description": "Internal Server Error",
                "model": ProblemResponse,
                "content": {"application/problem+json": {}},
            },
        },
    )
    app.state.logger = configure_logging()
    app.add_middleware(RequestIdMiddleware)
    app.add_exception_handler(HTTPException, http_problem)
    app.add_exception_handler(RequestValidationError, validation_problem)
    app.add_exception_handler(Exception, unhandled_problem)
    trip_planning = TripPlanning(
        StaticServiceStatus(),
        unit_of_work_factory,
        FixtureTravelReadinessCapability(),
    )
    app.include_router(status_router(trip_planning))
    app.include_router(principal_router(access_token_verifier, planner_resolver))
    app.include_router(
        trip_router(trip_planning, access_token_verifier, planner_resolver)
    )
    app.include_router(
        run_router(trip_planning, access_token_verifier, planner_resolver)
    )
    app.include_router(
        plan_revision_router(trip_planning, access_token_verifier, planner_resolver)
    )
    install_problem_media_type(app)
    return app


def create_runtime_app() -> FastAPI:
    settings = RuntimeSettings.from_environment()
    (entry,) = settings.external_identity_allowlist
    database = PostgresDatabase(settings.database_url.get_secret_value())
    resolver = ResolvePlanner(
        PostgresExternalIdentityRepositoryFactory(database),
        AllowedExternalIdentity(
            issuer=entry.issuer,
            subject=entry.subject.get_secret_value(),
        ),
    )
    verifier: AccessTokenVerifier = RejectingAccessTokenVerifier()
    if settings.oidc_is_configured:
        issuer = settings.flash_trips_oidc_issuer
        audience = settings.flash_trips_oidc_client_id
        if issuer is None or audience is None:
            raise ValueError("OIDC verifier configuration must be complete")
        verifier = JwtAccessTokenVerifier(
            issuer=issuer,
            audience=audience,
            jwks_uri=settings.oidc_jwks_uri,
            allowed_algorithms=("RS256",),
            required_scope="principal:read",
        )
    return create_app(
        access_token_verifier=verifier,
        planner_resolver=resolver,
        database=database,
        unit_of_work_factory=PostgresUnitOfWorkFactory(database),
    )


__all__ = ["create_app", "create_runtime_app"]
