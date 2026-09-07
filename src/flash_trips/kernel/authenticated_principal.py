from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AuthenticatedPrincipal:
    """Provider-neutral identity established from an access token."""

    issuer: str
    subject: str
    scopes: frozenset[str]
