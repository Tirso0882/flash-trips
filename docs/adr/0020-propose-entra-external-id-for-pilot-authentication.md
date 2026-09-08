# Propose Entra External ID for pilot authentication

Status: Proposed, maintainer approval required

Date checked: 2026-09-08

## Proposal

Use Microsoft Entra External ID for the single-Planner pilot if the corrected
disposable registration passes the remaining live callback check. Keep Auth0
as the provider-neutral fallback. This record does not approve the choice.

The implementation depends only on OIDC discovery, Authorization Code with
PKCE, JWT/JWKS verification, and the application-owned External Identity and
session boundaries. Provider tokens remain in the Next.js BFF. Entra groups,
provider roles, and email equality grant no application access.

## Evidence

The deterministic suite proves the following without live credentials:

- the authorization request uses S256 PKCE, random state and nonce, the exact
  configured redirect URI, and Google federation;
- state, authorization-code, token-response, ID-token, and nonce failures issue
  no application session and return one non-enumerating Planner error;
- the callback consumes its encrypted ten-minute transaction cookie and issues
  only the opaque, revocable application cookie;
- FastAPI verifies the exact issuer, audience, asymmetric algorithm, lifetime,
  scope, and JWKS signature before exact `(issuer, subject)` resolution;
- token and authorization-code canaries do not enter responses, logs, or test
  evidence.

The disposable Entra tenant discovery check on 2026-09-08 found HTTPS
authorization, token, and JWKS endpoints on the configured tenant host and
advertised RS256 ID-token signing. It also found that the discovery document's
issuer host does not equal `FLASH_TRIPS_OIDC_ISSUER`; the scheme and
case-folded tenant path do match. Exact issuer validation therefore fails
closed. No authorization code or token was requested, captured, or recorded.
The authenticated Google callback remains unproved until the disposable
registration supplies the discovery issuer exactly.

## Current entitlement and cost

The [official Entra External ID pricing page](https://azure.microsoft.com/en-us/pricing/details/microsoft-entra-external-id/)
currently lists the Basic offering at USD 0 for the first 50,000 monthly active
users. The [official Auth0 pricing page](https://auth0.com/pricing) currently
lists Free at USD 0 per month for up to 25,000 monthly active users, with
passwordless authentication and unlimited social connections subject to its
stated system limits. Either identity tier costs USD 0 at one Planner.

The disposable tenant's actual subscription entitlement was not exposed by
the supplied runtime credentials, so it is not claimed as verified. A
maintainer must confirm the tenant is on the Entra External ID Basic
entitlement and recheck both offers before approval.

## Approval and disposal gate

Before approving this proposal, correct the configured issuer, run one
redacted Google callback through the exact registered redirect, verify
server-side sign-out and cookie replay denial, and record only pass/fail facts.
The development registration must remain separate from any hosted
registration.

The disposable registration and client secret are offered for explicit
transfer to the maintainer only if this proposal is approved. Otherwise the
tenant owner must delete the registration and secret after review. No supplied
credential is committed to this repository.
