# Identity and guest-session options for the Azure pilot

Date reviewed: 2026-08-20

## Question and constraints

This note establishes facts needed to choose the identity provider for an invitation-only Flash Trips pilot with 5–10 Planners, a Next.js frontend, a FastAPI backend, and Azure hosting. It compares Microsoft Entra External ID with Auth0, Clerk, and self-hosted Keycloak, then defines a provider-independent boundary for invitation eligibility, Trip ownership, browser guest sessions, and claim-after-login.

This is research input, not the product decision. Ticket #2 owns the final choice.

## Findings in brief

- Microsoft Entra External ID and Auth0 are the strongest managed, standards-based candidates. Both support OIDC and Authorization Code with PKCE, issue access tokens that FastAPI can validate through discovery metadata and JWKS, and have a free identity tier far above a 5–10 Planner pilot.[^entra-overview][^entra-supported][^entra-pricing][^auth0-pkce][^auth0-pricing]
- Entra External ID fits the accepted Azure deployment and can export logs to Azure Monitor. It also introduces a distinct external tenant, separate administration, and a monitoring setup that crosses back to a workforce tenant/subscription. Some external-tenant capabilities, including invited users, are documented as preview, so Flash Trips should not make its eligibility boundary depend on that feature.[^entra-create][^entra-supported][^entra-monitor]
- Auth0 is the strongest managed fallback when a conventional OIDC boundary and cloud neutrality matter more than one Microsoft control plane. Its free plan currently covers up to 25,000 monthly active users; its Next.js quickstart, API token-validation guidance, Dashboard, and Management API reduce integration effort.[^auth0-pricing][^auth0-nextjs][^auth0-validation][^auth0-users]
- Clerk is attractive for the fastest Next.js and invite-only experience, and its free plan currently includes up to 50,000 monthly retained users per app. It issues verifiable session JWTs, but Clerk explicitly says OAuth-based user registration and sign-in/out is not currently supported because it uses its own user-management architecture. It is therefore not equivalent to an interchangeable OIDC provider for this requirement.[^clerk-pricing][^clerk-nextjs][^clerk-restriction][^clerk-oauth][^clerk-token]
- Keycloak is a fully compliant OIDC provider and the strongest self-hosted portability option, but production operation includes TLS, hostname and proxy configuration, a production database, health/metrics, upgrades, backups, and normally multiple instances for availability. Its software licence may be free, but it adds infrastructure and security ownership that is disproportionate for this pilot.[^keycloak-oidc][^keycloak-container][^keycloak-production]
- The identity provider should authenticate a person only. Flash Trips should own invitation eligibility, the stable Planner record, Trip ownership, approvals, handbook access, guest-session state, and the one-time claim transaction. This boundary prevents provider groups, roles, invitations, or mutable email addresses from becoming domain authority.
- At pilot scale, all three managed options can plausibly have a USD 0 identity-tier charge if Flash Trips avoids SMS and paid add-ons. The meaningful cost comparison is therefore engineering and operational burden, not MAU price. Pricing and feature entitlements remain changeable and must be rechecked before release.

## Required authority boundary

Authentication answers: **which external identity authenticated this request?** It does not answer whether that identity is invited, owns a Trip, may approve a decision, or may access a Trip Handbook.

Flash Trips should persist these separate concepts:

| Concern | Authoritative owner | Minimum binding |
|---|---|---|
| Authentication | Identity provider | Valid token and external identity `(issuer, subject)` |
| Invitation eligibility | Flash Trips | Invitation ID, hashed secret, intended email or explicit administrator assignment, expiry, status |
| Planner | Flash Trips | Stable internal Planner ID mapped to one or more external identities |
| Trip ownership | Flash Trips | Trip ID → Planner ID |
| Approval authority | Flash Trips | Planner ID, Trip ownership, exact Approval Request and revision fingerprints |
| Handbook access | Flash Trips | Planner ownership and eligible approved Plan Revision |
| Guest session | Flash Trips | Opaque browser-bound session ID, expiry, provisional state, claim status |
| Claim after login | Flash Trips | One atomic transition from an unclaimed guest session to an eligible authenticated Planner |

The portable identity key is `(iss, sub)`, not email. OIDC defines `iss` as the issuer identifier and `sub` as a locally unique, never-reassigned identifier within that issuer. The pair is the stable lookup boundary across providers.[^oidc-core] Email can help match an invitation during first sign-in only when the provider marks it verified; after acceptance, ownership must bind to the internal Planner ID.

This design also contains migration cost. Changing providers requires affected Planners to authenticate or re-link an identity, but it does not require rewriting Trip ownership or Approval records.

## Comparison

| Criterion | Microsoft Entra External ID | Auth0 | Clerk | Self-hosted Keycloak |
|---|---|---|---|---|
| Standards fit | OIDC, OAuth 2.0, Authorization Code + PKCE supported in external tenants | OIDC-conformant applications and Authorization Code + PKCE | Verifiable Clerk session JWTs; not a standard OAuth user-management replacement | Fully compliant OIDC provider with discovery, authorization, token and JWK endpoints |
| Next.js path | MSAL/browser-delegated flow; more tenant and app-registration setup | First-party Next.js SDK and quickstart | Deep first-party Next.js SDK/components; lowest frontend effort | Generic OIDC library; Flash Trips owns integration and UI composition |
| FastAPI path | Validate API access token against tenant-specific metadata/JWKS, issuer and audience | Validate API access token signature, audience, permissions and standard claims | Validate Clerk-generated session JWT and expected audience/origin | Validate JWT against realm discovery/JWKS and configured audience |
| Invitation facilities | Admin-created accounts; external-tenant invited users documented as preview; user assignment is supported | Admin-created users; Organization invitations available | Built-in invite-only and waitlist access modes | Admin/user APIs and configurable flows, but Flash Trips would own invitation delivery and policy |
| Pilot identity-tier cost | USD 0 for core offer within first 50,000 MAU | USD 0 within free plan up to 25,000 MAU | USD 0 within free plan up to 50,000 MRU per app | USD 0 licence; non-zero Azure compute/database/operations |
| Azure integration | Strongest: Azure subscription setup and Azure Monitor export, but distinct tenant administration | Runs as external SaaS; straightforward HTTPS/JWKS integration | Runs as external SaaS; straightforward HTTPS/JWT integration | Must be deployed, patched, monitored and recovered on Azure |
| Local development | Loopback HTTP redirects supported; separate dev and production registrations recommended | Local callback/logout/origin URLs and separate tenants/apps | Dedicated development instance and SDK keys | Excellent local container `start-dev`, but local configuration must match production realm semantics |
| Portability | Standard runtime protocol; Microsoft-specific tenant, Graph and admin automation | Standard runtime protocol; Auth0 Actions/Organizations/Management API are proprietary | Highest application coupling of the managed options | Highest runtime portability and data control; highest operational burden |
| Main uncertainty/risk | External-tenant operational surface and preview invitation capability | Free-plan/feature changes and SaaS dependency | Does not meet a strict interchangeable-OIDC user-management requirement | Identity outage/security responsibility moves to the project |

### Microsoft Entra External ID

External ID creates a dedicated external tenant containing customer accounts, app registrations, user flows, sign-in methods and signing keys. External tenants support OIDC, Authorization Code, and Authorization Code with PKCE. User flows can offer email/password, email one-time passcode, social identities, Microsoft Entra ID, or custom OIDC federation.[^entra-overview][^entra-userflow][^entra-supported]

For Flash Trips, use browser-delegated authentication. Register the frontend/client and the FastAPI resource so the client requests an access token for the Flash Trips API audience. Microsoft documents PKCE support and recommends it for all application types; public clients must not hold a client secret.[^entra-authcode] The API must reject an access token unless its signature, exact issuer, intended audience, lifetime, and required scopes are valid. Microsoft explicitly warns that accepting a token for another audience is a confused-deputy vulnerability.[^entra-tokens]

Local loopback HTTP redirects are supported for active development. Microsoft recommends separate application registrations for development and production so unnecessary development redirects are not exposed in the production app.[^entra-redirect]

The pilot is comfortably inside the External ID core offer's first 50,000 free MAU. SMS phone authentication and premium capabilities are separately priced and have no free tier, so the pilot estimate assumes email-based sign-in and no premium add-on.[^entra-pricing]

The Azure fit is real but not frictionless:

- Creating a paid external tenant requires an Azure subscription and Tenant Creator permission; the tenant is then administered separately in Microsoft Entra and Azure portals.[^entra-create]
- External-tenant logs can be sent to Azure Storage, Log Analytics, or Event Hubs, but the current setup authenticates against a workforce tenant subscription and uses a wizard/Azure Lighthouse relationship.[^entra-monitor]
- External tenants support user assignment and app roles, but those should remain defence-in-depth only. Invited users are currently listed as preview, while self-service sign-up and admin-created customer accounts are established paths.[^entra-supported][^entra-manage]

Consequently, Entra can authenticate invited Planners without becoming the invitation database. Flash Trips can pre-create or allow an identity account, then still deny application access unless its external identity resolves to an active internal invitation and Planner.

### Auth0

Auth0 supplies an OIDC-conformant hosted identity service, a Next.js quickstart/SDK, configurable application callback URLs, and API access tokens. Its guidance requires an API to validate the JWT, audience, permissions/scopes, and standard claims, returning `401` when validation fails.[^auth0-nextjs][^auth0-settings][^auth0-validation]

The free plan currently includes up to 25,000 monthly active users, one custom domain, social connections, and five Organizations. That is far beyond pilot demand, but the price page is a current offer rather than a durable architectural guarantee.[^auth0-pricing]

Auth0 can create users through its Dashboard or Management API and can send expiring Organization membership invitations.[^auth0-users][^auth0-invitations] Flash Trips does not need to adopt Organizations for a single-Planner invitation pilot. Doing so would create a second membership model and couple authorisation to a proprietary API. Retaining an internal invitation table while using Auth0 only for authentication preserves the same boundary proposed for Entra.

Auth0 has lower Azure-specific integration than Entra, but that is also its portability advantage: FastAPI depends on ordinary OIDC/JWT configuration, while Azure only needs outbound HTTPS access and application configuration. Operational evidence is split between Auth0 logs and Azure telemetry.

### Clerk

Clerk has the most direct Next.js developer experience and exposes invite-only, open, and waitlist access modes. In invite-only mode, only a valid invitation can reach sign-up. Clerk also publishes a token verifier that checks its generated JWT via a supplied public key or fetched JWKS, with audience and authorised-party checks.[^clerk-nextjs][^clerk-restriction][^clerk-token]

Its current free plan includes 50,000 monthly retained users per app and requires no identity-tier payment at pilot volume.[^clerk-pricing]

However, Clerk's own OAuth/OIDC overview says that OAuth user management—a full registration and sign-in/out authorization service—is not currently supported because Clerk uses its own architecture.[^clerk-oauth] Flash Trips could still integrate Clerk session JWTs with FastAPI, but the frontend, session lifecycle, and invitation flow would be Clerk-shaped. Choose it only if rapid UX delivery is deliberately more important than the accepted OIDC/PKCE portability target.

### Keycloak

Keycloak exposes standard OIDC discovery, authorization, token, user-info, logout, JWK, introspection and revocation endpoints. It supports Authorization Code and can be run locally in a container, which makes it a useful portability reference and offline development option.[^keycloak-oidc][^keycloak-container]

For production, the project would own a hardened image, TLS, hostname and reverse-proxy behaviour, a production database, health and metrics endpoints, patches, backups, recovery, and identity availability. Keycloak's own production guidance normally recommends two or more instances so sign-in can continue after one instance fails.[^keycloak-production] This is a poor trade for 5–10 Planners unless operating identity infrastructure is itself a learning objective.

## Recommended protocol and API contract

Use one provider adapter with configuration for issuer, client ID, API audience, scopes, redirect URIs and discovery URL. Keep provider SDK objects out of the domain model.

The runtime sequence should be:

1. Next.js starts an OIDC Authorization Code flow with PKCE against the configured provider.
2. The provider authenticates the person and returns an authorization code to an exact registered redirect URI.
3. The client exchanges the code and obtains an access token intended for the Flash Trips FastAPI audience.
4. FastAPI validates the access token before constructing an `AuthenticatedPrincipal` containing the external `(issuer, subject)` and safe required claims.
5. Flash Trips resolves that external identity to an active Planner and checks invitation eligibility and Trip ownership for every protected operation.
6. The identity token/session is never used directly as evidence of Trip ownership, Approval authority, or handbook access.

FastAPI validation must fail closed and should include:

- allowed signing algorithm and valid signature using cached discovery/JWKS keys;
- exact configured issuer and API audience;
- expiry and not-before checks with small bounded clock skew;
- the required delegated scope/permission for the endpoint;
- optional authorised client/party check when the provider exposes it;
- a bounded JWKS refresh on an unknown key ID, not an unbounded provider call per request;
- rejection of ID tokens and access tokens issued for Microsoft Graph or another API.

Offline tests should use a deterministic local test issuer/key pair and cover wrong issuer, audience, algorithm, key, expiry, scope, and identity mapping. Interactive local development should use a dedicated development tenant/application and loopback redirect, never a production validation bypass.

## Browser guest session and claim-after-login

Guest access does not require an anonymous identity-provider account. Flash Trips should issue a high-entropy opaque guest-session token in a `Secure`, `HttpOnly`, appropriately `SameSite` cookie and store only server-side session state with an absolute expiry. OWASP recommends cookies as the session exchange mechanism, meaningless/high-entropy session identifiers, HTTPS for the entire session, `Secure` and `HttpOnly` cookie attributes, and session-ID renewal after a privilege change.[^owasp-session]

An unauthenticated visitor may use that guest session for general travel questions and provisional recommendations. The guest boundary must not permit:

- creation of a saved private Trip or Plan Revision;
- cross-device continuation;
- an Approval;
- access to a Trip Handbook;
- ownership or permission decisions.

Claiming should be an explicit, audited transaction after authentication:

1. The browser possesses the unexpired guest cookie and completes provider authentication.
2. FastAPI validates the access token and resolves an eligible internal Planner through the Flash Trips invitation record.
3. A single database transaction locks the guest session, verifies that it is unclaimed, and creates or attaches the resulting Trip to that Planner.
4. If the guest session was already claimed by a different Planner, the operation fails without copying or disclosing its state.
5. Flash Trips records the claim, rotates or invalidates the guest token, and creates the authenticated session boundary.
6. A replay returns the same result only for the same Planner and idempotency key; it never transfers ownership again.

Possession of an invitation link alone is not authentication, and possession of a guest cookie alone is not authorisation. State-changing cookie-authenticated endpoints also require CSRF defences; `SameSite` is defence in depth rather than a complete substitute.[^owasp-csrf]

## Research recommendation for ticket #2

Carry two providers into the decision:

1. **Microsoft Entra External ID** as the leading Azure-aligned candidate. It satisfies the protocol and pilot-cost requirements and centralises more operational evidence in Azure.
2. **Auth0** as the managed standards-based fallback. It offers a simpler cloud-neutral boundary and mature application/API integration without self-hosting.

Do not carry Clerk as an equal OIDC candidate unless ticket #2 explicitly relaxes the interoperable OIDC user-management requirement. Do not self-host Keycloak for the initial pilot unless identity operations are intentionally added to the learning scope.

Before the product decision, run one small, disposable integration spike for Entra and Auth0 using the same acceptance contract:

- Next.js Authorization Code + PKCE sign-in and sign-out;
- FastAPI API-audience token validation and negative cases;
- internal invitation acceptance and uninvited `403`;
- guest-session claim with replay and cross-Planner rejection;
- local loopback development;
- test-environment configuration and redacted authentication telemetry;
- account disable/revocation behaviour and a documented recovery path.

Prefer Entra if it passes that contract without relying on preview invitations or placing domain permissions in Entra groups. Prefer Auth0 if Entra's distinct-tenant administration, local integration, or diagnostics impose materially more complexity. The spike should decide with evidence; this research does not make that product choice.

## Uncertainties to retain

- Managed-provider pricing and free-plan entitlements can change. Recheck immediately before the invitation pilot; the estimates exclude SMS, premium MFA, paid custom domains, email-delivery services and support plans.
- Microsoft's external-tenant feature matrix is evolving. Invited users are currently marked preview, and monitoring crosses tenant/subscription boundaries; neither should be assumed production-stable without a spike.[^entra-supported][^entra-monitor]
- Provider logout and revocation do not instantly invalidate every already-issued JWT in all topologies. The implementation must test disabled-account and revoked-session behaviour against the chosen token lifetime rather than infer it from sign-out UI.
- No managed-provider choice eliminates application security work. Flash Trips still owns CSRF defence, token-to-Planner mapping, invitation lifecycle, ownership checks, audit records, guest expiry, claim idempotency, and data retention.

## Sources

[^entra-overview]: Microsoft Learn, [Overview: Secure your apps using External ID in an external tenant](https://learn.microsoft.com/en-us/entra/external-id/customers/overview-customers-ciam).
[^entra-supported]: Microsoft Learn, [Supported features in workforce and external tenants](https://learn.microsoft.com/en-us/entra/external-id/customers/concept-supported-features-customers).
[^entra-userflow]: Microsoft Learn, [Create a sign-up and sign-in user flow for an external tenant app](https://learn.microsoft.com/en-us/entra/external-id/customers/how-to-user-flow-sign-up-sign-in-customers).
[^entra-manage]: Microsoft Learn, [Manage customer accounts](https://learn.microsoft.com/en-us/entra/external-id/customers/how-to-manage-customer-accounts).
[^entra-authcode]: Microsoft Learn, [OAuth 2.0 authorization code flow](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-auth-code-flow).
[^entra-tokens]: Microsoft Learn, [Access tokens in the Microsoft identity platform](https://learn.microsoft.com/en-us/entra/identity-platform/access-tokens).
[^entra-redirect]: Microsoft Learn, [Redirect URI (reply URL) restrictions and limitations](https://learn.microsoft.com/en-us/entra/identity-platform/reply-url).
[^entra-pricing]: Microsoft Azure, [Microsoft Entra External ID pricing](https://azure.microsoft.com/en-us/pricing/details/microsoft-entra-external-id/).
[^entra-create]: Microsoft Learn, [Create an external tenant](https://learn.microsoft.com/en-us/entra/external-id/customers/how-to-create-external-tenant-portal).
[^entra-monitor]: Microsoft Learn, [Set up Azure Monitor in external tenants](https://learn.microsoft.com/en-us/entra/external-id/customers/how-to-azure-monitor).
[^auth0-pricing]: Auth0, [Pricing](https://auth0.com/pricing).
[^auth0-pkce]: Auth0 Docs, [Authorization Code Flow with Proof Key for Code Exchange (PKCE)](https://auth0.com/docs/get-started/authentication-and-authorization-flow/authorization-code-flow-with-pkce).
[^auth0-nextjs]: Auth0 Docs, [Next.js quickstart](https://auth0.com/docs/quickstart/webapp/nextjs).
[^auth0-validation]: Auth0 Docs, [Validate access tokens](https://auth0.com/docs/secure/tokens/access-tokens/validate-access-tokens).
[^auth0-settings]: Auth0 Docs, [Application settings](https://auth0.com/docs/get-started/applications/application-settings).
[^auth0-users]: Auth0 Docs, [Create users](https://auth0.com/docs/manage-users/user-accounts/create-users).
[^auth0-invitations]: Auth0 Docs, [Send Organization membership invitations](https://auth0.com/docs/manage-users/organizations/configure-organizations/send-membership-invitations).
[^clerk-pricing]: Clerk, [Pricing](https://clerk.com/pricing).
[^clerk-nextjs]: Clerk Docs, [Next.js quickstart](https://clerk.com/docs/nextjs/getting-started/quickstart).
[^clerk-restriction]: Clerk Docs, [Restrict access to your application](https://clerk.com/docs/guides/secure/restricting-access).
[^clerk-token]: Clerk Docs, [`verifyToken()`](https://clerk.com/docs/reference/backend/verify-token).
[^clerk-oauth]: Clerk Docs, [OAuth and OIDC overview](https://clerk.com/docs/guides/configure/auth-strategies/oauth/overview).
[^keycloak-oidc]: Keycloak, [Securing applications and services with OpenID Connect](https://www.keycloak.org/securing-apps/oidc-layers).
[^keycloak-container]: Keycloak, [Running Keycloak in a container](https://www.keycloak.org/server/containers).
[^keycloak-production]: Keycloak, [Configuring Keycloak for production](https://www.keycloak.org/server/configuration-production).
[^oidc-core]: OpenID Foundation, [OpenID Connect Core 1.0, Subject Identifier and Issuer Identifier](https://openid.net/specs/openid-connect-core-1_0.html#Terminology).
[^owasp-session]: OWASP Cheat Sheet Series, [Session Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html).
[^owasp-csrf]: OWASP Cheat Sheet Series, [Cross-Site Request Forgery Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html).
