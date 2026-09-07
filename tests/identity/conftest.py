from collections.abc import Generator

import pytest

from .local_issuer import LocalOidcIssuer, serving_local_oidc_issuer


@pytest.fixture
def local_oidc_issuer() -> Generator[LocalOidcIssuer]:
    with serving_local_oidc_issuer() as issuer:
        yield issuer
