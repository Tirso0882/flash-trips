# Use External ID behind application-owned access

Flash Trips will use Microsoft Entra External ID as its intended identity provider for the invitation-only pilot, offering Google federation and email one-time-code sign-in through a Next.js backend-for-frontend. Entra authenticates an External Identity, while Flash Trips remains authoritative for Invitations, Planner identity, linked sign-in methods, Planner Access Status, Operator authority, Trip ownership, Approvals, and handbook access. This preserves an OIDC boundary without allowing provider accounts, groups, or mutable email addresses to become domain permissions.

## Considered Options

- Auth0 remains the managed OIDC fallback because it provides a similar standards-based application boundary with less Azure-specific administration.
- Direct Google authentication was rejected because it would make one social provider the application's identity boundary and complicate adding another sign-in method.
- Automatic same-email account linking was rejected because email equality does not prove that two provider identities belong to the same Planner.
- Identity-provider invitations and groups were rejected as domain authority because Flash Trips must enforce eligibility and ownership independently of provider features.

## Consequences

Entra becomes the final implementation commitment only after a disposable integration spike verifies Google and email-code sign-in, the Next.js session boundary, FastAPI API-audience token validation, internal Invitation enforcement, safe account linking, guest transition, immediate suspension, Operator bootstrap, local development, and redacted telemetry without preview invitations or provider groups. Auth0 is selected instead if a correctness or security requirement needs an unstable feature or disproportionate workaround.

The browser receives only secure HTTP-only application cookies; Entra access tokens remain server-side and FastAPI validates their signature, issuer, audience, lifetime, and scope before resolving `(issuer, subject)` to exactly one active Planner. Flash Trips never creates or links a Planner from email equality alone. Linking another verified External Identity requires recent authentication through an already linked method or Operator-assisted recovery, and initial unlinking is Operator-assisted and cannot remove the final usable identity.

An Invitation is application-owned, bound to one verified email, valid for seven days, accepted once, and administered only by an Operator. Continuing eligibility is controlled separately through `Active`, `Suspended`, and `Closed` Planner Access Status values. Suspension blocks protected operations immediately; closure leaves data disposition to the security, privacy, and retention policies.

An unauthenticated visitor receives only rate-limited, cited general travel answers through a browser-bound Guest Session. The session permits neither personalised planning nor inventory searches, Trip ownership, Plan Revisions, Approvals, cross-device continuation, or handbook access; it expires after 24 hours of inactivity or seven days absolutely. After sign-in, a visitor may explicitly confirm travel details to create a Trip Request, but guest conversation content never becomes authoritative automatically.

Flash Trips owns Planner Profile and optional marketing-consent records, but the exact captured fields, website forms, progressive-profile experience, campaign policy, and retention rules are deferred to their dedicated UX, privacy, and persistence decisions.
