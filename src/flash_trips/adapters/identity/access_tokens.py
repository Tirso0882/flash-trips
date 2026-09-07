from flash_trips.application import AccessTokenVerificationError
from flash_trips.kernel.authenticated_principal import AuthenticatedPrincipal


class RejectingAccessTokenVerifier:
    """Fail-closed verifier used until a configured verifier is composed."""

    def verify(self, access_token: str) -> AuthenticatedPrincipal:
        del access_token
        raise AccessTokenVerificationError
