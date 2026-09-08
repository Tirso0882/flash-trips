# Use Entra External ID for pilot authentication

Status: Accepted

Date checked: 2026-09-08

## Decision

Use Microsoft Entra External ID for the single-Planner pilot. Keep Auth0 as the
provider-neutral fallback.

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

The disposable Entra tenant checks on 2026-09-08 found that the exact discovery
issuer uses `<tenant-id>.ciamlogin.com`, while the authorization, token, and
JWKS endpoints use `<tenant-subdomain>.ciamlogin.com`. The corrected
configuration matches that issuer exactly. All three service endpoints use
HTTPS, discovery advertises RS256 ID-token signing, and a live authorization
request with S256 PKCE and the exact registered redirect reached the tenant's
Google sign-in surface without a provider error. The token endpoint rejected a
synthetic invalid code and verifier. No authorization code or token was
captured or recorded.

The authenticated Google callback then completed through the exact HTTPS
redirect. The one-time verifier exchanged the authorization code with its S256
verifier and validated the ID token's RS256 signature, exact issuer, audience,
state, and nonce. It reported only pass or fail and retained no authorization
code, provider token, identity claim, or private payload.

## Current entitlement and cost

The [official Entra External ID pricing page](https://azure.microsoft.com/en-us/pricing/details/microsoft-entra-external-id/)
currently lists the Basic offering at USD 0 for the first 50,000 monthly active
users. The [official Auth0 pricing page](https://auth0.com/pricing) currently
lists Free at USD 0 per month for up to 25,000 monthly active users, with
passwordless authentication and unlimited social connections subject to its
stated system limits. Either identity tier costs USD 0 at one Planner.

The supplied runtime credentials did not expose billing information. On
2026-09-08, the maintainer instead confirmed through the Entra administrative
surface that the disposable external tenant has a linked Azure subscription
and no premium External ID add-ons. The maintainer also rechecked both
published identity-tier prices. The Basic/core Entra tier and Auth0 Free tier
therefore each cost USD 0 at the pilot's current scale.

## Retention and telemetry

The [official Entra retention documentation](https://learn.microsoft.com/en-us/entra/identity/monitoring-health/reference-reports-data-retention)
states that External ID Basic retains logs for seven days and requires Azure
Monitor for longer retention. External tenants record audit, sign-in, and
sign-up activity. The [official Auth0 retention table](https://auth0.com/docs/deploy-monitor/logs/log-data-retention)
does not state a retention period for the Free plan. The
[official Auth0 log documentation](https://auth0.com/docs/deploy-monitor/logs/pii-in-logs)
states that authentication logs can contain personal data, including names,
email addresses, phone numbers, IP addresses, and custom fields. It excludes
access tokens, identity-provider tokens, private keys, and other core secrets,
and records authorization codes only in partial form.

## Maintainer approval

On 2026-09-08, the maintainer approved this decision after reviewing the live
Google PKCE callback, deterministic failure coverage, session revocation, safe
errors, secret redaction, current entitlement, pricing, retention, telemetry,
and the final green pull-request checks.

The maintainer accepted custody of the disposable Entra tenant, local
development registration, client secret, Google OAuth client, and Google
project so live sign-in can continue. The local registration is not used by a
hosted environment. Any hosted environment requires a separate registration,
client ID, secret, and exact redirect URI. No supplied credential is committed
to this repository or provided to pull-request workflows.
