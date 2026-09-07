from typing import Protocol

from flash_trips.kernel.authenticated_principal import AuthenticatedPrincipal
from flash_trips.kernel.service_status import ServiceStatus


class ServiceStatusPort(Protocol):
    def read(self) -> ServiceStatus: ...


class AccessTokenVerifier(Protocol):
    def verify(self, access_token: str) -> AuthenticatedPrincipal: ...


class AccessTokenVerificationError(Exception):
    """An access token could not establish an authenticated principal."""
