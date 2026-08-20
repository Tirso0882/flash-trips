# Git branching and budget infrastructure

Date reviewed: 2026-08-19

## Decisions in brief

- Use one long-lived branch: `main`. Develop on short-lived issue/feature branches and merge through pull requests.
- `test` and `production` are deployment environments, not Git branches. Automatically deploy a successful `main` artefact to test; manually promote that exact artefact to production.
- Keep FastAPI, Next.js, LangGraph, PostgreSQL, and Docker. Azure is a deployment choice, not an architectural requirement.
- Default low-cost invitation stack: Railway Hobby running separate Next.js, FastAPI, and PostgreSQL services, with an external OIDC identity provider and Redis omitted initially. Add scheduled database backups and an independent off-site `pg_dump`.
- Near-zero hosted prototype: Vercel Hobby for Next.js, Render Free for FastAPI, Supabase Free for PostgreSQL/auth, and Upstash Free only if Redis becomes necessary. This is suitable for a demo, not durable saved trips.
- True zero-cloud-cost development: Docker Compose locally, provider fixtures, and optionally a local model. It is not an available hosted service and still consumes local hardware/electricity.

## 1. Branch and environment strategy

### Recommended flow

```text
feature/<issue>-<slug> -> pull request -> main
                                         |
                                         +-> build immutable artefact once
                                                |
                                                +-> automatic test deployment
                                                +-> manual production promotion
```

GitHub describes GitHub Flow as a lightweight branch-based workflow: create a branch, commit, open a pull request, merge into the default branch, then delete the branch.[^github-flow] That is enough for one developer.

Use:

- protected `main` as the only long-lived source branch;
- short-lived `feature/<issue>-<slug>`, `fix/<issue>-<slug>`, or `docs/<issue>-<slug>` branches;
- required CI checks, resolved conversations, and preferably squash merge;
- automatic branch deletion after merge;
- optional immutable release tags such as `v0.1.0`, only when releases become meaningful.

Do **not** create `dev`, `test`, and `prod` branches. They duplicate environment state in Git history and invite merge-forward/cherry-pick drift. A commit may pass test on one branch while production receives a different merge commit. Environment-specific configuration also does not belong in source branches.

Instead:

1. Pull-request CI validates the candidate commit without provider calls.
2. Merging to `main` builds each container once and identifies it by commit SHA/digest.
3. The digest is deployed automatically to `test`.
4. Production promotion is manually triggered and deploys the already-tested digest; it never rebuilds.
5. A hotfix is another short-lived branch from `main`, not a commit made directly to a production branch.

GitHub Environments are designed to apply deployment protection rules, branch/tag restrictions, and environment-scoped secrets before a deployment job runs.[^github-environments] They model `test` and `production` better than branches. Use deployment concurrency so only one deployment per target runs at once.[^github-concurrency]

### Private-repository caveat

For private repositories, GitHub Environments require GitHub Pro, Team, or Enterprise; on GitHub Free they are available only for public repositories. Required reviewers and wait timers also have plan/repository limitations.[^github-environments]

If this private repository remains on GitHub Free, keep the same one-branch strategy and use:

- automatic test deployment from `main`;
- a manually dispatched production workflow requiring an explicit commit SHA/digest;
- separate deployment credentials/configuration in the hosting platform;
- a workflow check that production input equals an artefact previously tested successfully.

Do not add environment branches merely to work around a GitHub plan limitation.

## 2. Infrastructure options without Azure

### What does not change

The accepted modular-monolith design is portable. Keep:

- Next.js as the web client;
- FastAPI as the application/streaming boundary;
- LangGraph as private durable-workflow machinery;
- PostgreSQL as canonical Trip, Plan Revision, Evidence, approval, event, and checkpoint storage;
- Docker Compose for the local production-shaped topology;
- narrow reasoning/provider ports so Azure OpenAI can be replaced without changing domain modules.

Redis is not canonical storage. For one API instance and invitation-only traffic, omit it initially or use an in-process limiter with the known limitation that counters reset on restart. Add Redis when rate limits, locks, or queues must be shared across replicas/processes.

### Option comparison

| Option | Cost posture | Streaming and workflows | Data/auth | Main trade-off |
|---|---|---|---|---|
| Local Docker Compose | No cloud bill | Full SSE and worker control while the machine is running | Local PostgreSQL; local Redis optional | Not reliably internet-accessible or highly available |
| Vercel + managed backend/database | Free/low-cost entry, several vendors | Vercel supports streaming, but Hobby functions have a five-minute maximum; keep long-running FastAPI/LangGraph work on a container backend | Supabase can combine PostgreSQL and auth; Upstash is optional Redis | Lowest frontend operations, but split observability and free-tier durability limits |
| Railway | USD 5/month Hobby minimum including USD 5 usage, then metered resources (reviewed 2026-08-19) | Long-lived containers; HTTP requests can run up to 15 minutes while data keeps flowing, or close after five idle minutes; WebSockets are exempt | PostgreSQL/Redis can run as services with volume backups; auth remains external | Cheapest coherent managed default, but usage is not capped at USD 5 and volume backups are not PITR |
| Render | Free prototype or paid services | FastAPI/Docker supported; free services spin down after 15 idle minutes | Free PostgreSQL expires after 30 days and has no backups; free Key Value is non-persistent | Free tier is unsuitable for authoritative saved trips |
| Hetzner VM + Docker Compose | Low fixed VM cost plus storage/backup/IP choices | Full SSE, workers, and containers under your control | Self-managed PostgreSQL, Redis, TLS, auth integration, backups | Lowest infrastructure price can become the highest operations burden |

#### Local-only / zero cloud cost

Run Next.js, FastAPI, PostgreSQL, and optional Redis with Docker Compose. Use deterministic fakes/recorded provider responses and a local model where hardware permits. This is the best development environment and the only honest zero-cloud-cost option.

Do not represent it as an invitation service unless the machine, network exposure, TLS, backups, monitoring, and uptime are deliberately operated.

#### Managed low-operations split stack

A common split is:

- Vercel Hobby for the personal, non-commercial Next.js frontend;
- Railway or Render for the FastAPI container/worker;
- Supabase for PostgreSQL and authentication;
- Upstash only when shared Redis is justified.

Vercel states that Hobby is free for personal, non-commercial projects. Its Functions support streaming, but the Hobby maximum duration is five minutes and streamed time counts toward that duration.[^vercel-hobby][^vercel-functions] Therefore the browser may be on Vercel, but Flash Trips' authoritative workflow should remain on FastAPI/container infrastructure and persist events for SSE reconnection.

Supabase Free currently includes two active projects, a 500 MB database, 50,000 monthly active auth users, and pauses projects after one week of inactivity. It does not provide managed daily backups; Supabase recommends free-tier users perform `db dump` and retain off-site backups. Pro starts at USD 25/month and includes seven days of daily backups (reviewed 2026-08-19).[^supabase-pricing][^supabase-backups]

Upstash Free currently includes 256 MB and 500,000 Redis commands per month, but has no SLA or multi-zone HA. Use it for replaceable limits/cache state, never Plan or workflow truth.[^upstash-pricing]

#### Railway all-in-one PaaS

Railway Hobby is the recommended first invitation deployment because it can run the existing containers and PostgreSQL in one project without introducing cloud-specific application code. Railway documents a USD 5/month Hobby subscription that includes USD 5 of usage; CPU, RAM, storage, and egress beyond that are metered.[^railway-pricing]

Deploy separate services from the same repository:

- Next.js;
- FastAPI (initially also executing resumable work);
- PostgreSQL;
- optional worker only after measured need;
- optional Redis only after shared coordination is needed.

Railway's edge supports HTTP/1.1, HTTP/2, and WebSockets. HTTP requests can run for up to 15 minutes while data continues to transfer and otherwise close after five minutes without data.[^railway-networking] Send SSE heartbeats, but never make the connection the workflow owner: persist run events/checkpoints and let clients reconnect by cursor. Move execution to a worker when a run must outlive an API process/request.

Railway supports manual and scheduled incremental volume backups, including database volumes, but restore is limited to the same project/environment and the feature has documented limitations.[^railway-backups] Keep a second logical `pg_dump` outside the project and test restores.

#### Render

Render is viable on paid instances, but its free services are for prototypes. Render documents that free web services spin down after 15 minutes without inbound traffic and use an ephemeral filesystem. Its free PostgreSQL expires after 30 days and has no backups; free Redis-compatible Key Value is in-memory and loses data on restart.[^render-free] Paid Render PostgreSQL receives continuous backups and point-in-time recovery.[^render-backups]

This makes `Vercel + Render Free + Supabase Free` a useful nearly free demo stack, but not an invitation release with durable private trips.

#### Hetzner VPS / self-hosted Compose

A single Hetzner Cloud VM can run Caddy, Next.js, FastAPI, a worker, PostgreSQL, and Redis through Docker Compose. Hetzner bills servers hourly up to a monthly cap and charges server Backups at 20% of the server price for seven backup slots.[^hetzner-billing]

This offers excellent cost/control and natural support for SSE and long-running workers, but you own OS/container patching, firewalling, TLS, secrets, monitoring, database tuning, upgrades, off-site backups, and restore drills. A single VM is also a single failure domain. Prefer it only if infrastructure operations are part of the learning goal.

## 3. Recommended adoption path

### Near-zero prototype

1. Develop with Docker Compose, local PostgreSQL, provider fixtures, and optional local inference.
2. If a public demo is needed, use Vercel Hobby + Render Free + Supabase Free/auth; omit Redis unless required.
3. Disable live provider/model calls by default and expose only seeded/demo trips.
4. Export Supabase data off-site because free-tier backups are not managed.
5. Label this clearly as a prototype: cold starts, inactivity pauses, and weak recovery are expected.

### Default invitation-only deployment

1. Use Railway Hobby for Next.js, FastAPI, and PostgreSQL containers/services.
2. Use a replaceable OIDC identity provider and enforce invitation/ownership in Flash Trips.
3. Start with one application instance; omit Redis and a separate worker until evidence requires them.
4. Persist LangGraph checkpoints and replayable run events in PostgreSQL; SSE is a view of durable state.
5. Configure scheduled Railway volume backups plus independent off-site logical backups and verify a restore.
6. Add a separate worker and Redis only when runs outlive requests or concurrency requires cross-process coordination.

This is production-shaped for a small invitation group, not highly available production. The first paid upgrade should protect the canonical database/backups, not add more agents or model capacity.

## 4. External model and travel-provider costs

Cheaper hosting does not remove model, search, maps, flight, or hotel-provider costs. Treat them as separate budgets:

- keep all CI and most development on fakes/cached evidence;
- route greetings deterministically and ambiguous shallow classification to a small model;
- reserve stronger models for bounded tasks that need them;
- set per-run call, token, timeout, and currency ceilings in `ReasoningRuntime`;
- require explicit approval for live EDD capture/model judges/provider canaries;
- store cost and provider-call lineage in `RunInspector`;
- never let a free-tier cache miss silently become a paid call.

Do not choose a permanent model vendor now. The existing typed reasoning port should allow local inference during development and a hosted provider for invitation runs without changing domain authority.

## 5. Workload cost model

### Scope and assumptions

This comparison models one invitation-only pilot for 5–10 planners, not a highly available public production service. It assumes:

- one Next.js service, one FastAPI/LangGraph service, and one PostgreSQL database;
- low concurrency and less than roughly 20 GB/month of outbound traffic;
- 5–10 GB of initial database/volume storage;
- replayable PostgreSQL events and checkpoints, with SSE as a reconnectable view;
- no Redis, dedicated worker, replicas, private networking, or paid observability add-ons initially;
- local/cached development and provider-free CI;
- a test application that is stopped or scales to zero except during deployment smoke tests;
- 730 hours in the illustrative monthly calculations.

Model, search, maps, flight, hotel, identity-provider, domain-name, tax, and VAT charges are excluded. The estimates are planning ranges in USD unless marked otherwise, not provider quotations. Actual memory use is especially important on usage-metered platforms, so measure it during the first pilot month.

### Comparable monthly view

| Deployment | Near-zero/demo posture | Credible small-pilot estimate | Cost shape | Recovery and operational reality |
|---|---:|---:|---|---|
| Azure Container Apps + ACR + Azure PostgreSQL | Not meaningfully zero because PostgreSQL and ACR remain allocated | **~$24–40** for one small production environment; **~$43–60** if test has its own continuously allocated database | PostgreSQL and ACR are fixed; Container Apps, requests, logs, and egress are usage-based | Best managed database recovery in this set: automatic backups and 7–35 day PITR; the cheapest burstable server is not HA |
| Railway all-in-one | $5 minimum, but a real always-on database normally exceeds the included usage | **~$12–25**; allow **~$15–30** until measured | $5 minimum includes $5 usage; RAM, CPU, volume, and egress are metered | Coherent platform and low operations, but PostgreSQL is a service on a persistent volume rather than a managed HA database; keep an off-platform logical backup |
| Vercel + Railway API + Supabase | **~$5–10** with Vercel Hobby, Railway, and Supabase Free | **~$30–40** with Supabase Pro daily backups; add Vercel Pro if Hobby terms do not fit | Railway is metered/minimum; Supabase Pro is fixed; Vercel Hobby is free only for eligible personal non-commercial use | Good managed database/auth story on Pro, but three platforms create split logs, secrets, networking, and incident diagnosis |
| Render | **$0** with free web/API plus Supabase Free, accepting sleep and weak recovery | **~$20–33** for two Starter services and a paid PostgreSQL tier | Mostly predictable fixed instance prices; bandwidth/storage can add usage charges | Paid Render PostgreSQL has continuous backup/PITR; Free web services sleep and Free PostgreSQL has no backups, so Free is demo-only |
| Hetzner VPS + Docker Compose | No free hosted tier | **roughly EUR 6–14** for a small VM plus IPv4/backups/storage choices | Low, mostly fixed server price | Lowest plausible cash bill, but one VM is one failure domain and the developer owns patching, TLS, monitoring, PostgreSQL maintenance, off-site backup, and restore drills |

These ranges deliberately do not price a permanently warm, fully isolated test environment. Keeping an entire second environment online can nearly double compute/database cost on the smaller stacks. For this solo pilot, deploy test on demand, run smoke tests, and then scale it down. Keep production and test data logically separated; use a separately allocated database later when the recovery and isolation requirement justifies the cost.

### How the estimates were derived

#### Azure

The Azure Retail Prices API returned, for West Europe on 2026-08-19, a PostgreSQL Flexible Server B1ms/B1MS burstable compute price of $0.0199/hour and storage of $0.1369/GB-month. At 730 hours with the 32 GB minimum storage assumption, that is approximately `$14.53 compute + $4.38 storage = $18.91/month`. The same API returned ACR Basic at $0.1666/day, approximately $5.07 for 30.4 days.[^azure-retail-api]

Container Apps Consumption includes 180,000 vCPU-seconds, 360,000 GiB-seconds, and two million requests per subscription each month before usage charges.[^azure-container-apps-pricing] A very low-traffic pilot with both applications allowed to scale to zero can therefore keep Container Apps compute close to $0, leaving roughly $24/month before logs and egress. Keeping both applications warm, increasing resources, or generating significant logs moves the realistic total toward $40. A separate always-on B1ms test database adds roughly another $19/month.

Azure PostgreSQL automatically backs up the database and supports PITR over a configurable 7–35 day retention window.[^azure-postgres-backups] This is materially stronger recovery than a database container on a volume, but the entry burstable instance is still a single small database rather than an HA production topology.

#### Railway all-in-one

Railway Hobby costs at least $5/month and includes $5 of resource usage. Current documented rates are $10/GB-month of RAM, $20/vCPU-month of CPU, $0.15/GB-month for volumes, and $0.05/GB egress.[^railway-pricing]

For this topology, a measured average of roughly 1.0–1.5 GB RAM across Next.js, FastAPI, and PostgreSQL contributes $10–15/month. Low average CPU, 5–10 GB of volume, and light egress plausibly add another $2–7. That yields the $12–25 planning range; $15–30 is the safer initial budget until real resident memory and checkpoint growth are observed.

This is the cheapest coherent managed application platform in the comparison. Its trade-off is database operations: Railway volume snapshots are useful but are not PostgreSQL PITR, restore is scoped to the Railway project/environment, and documented backup limitations remain.[^railway-backups] Schedule snapshots and also export encrypted `pg_dump` backups outside Railway.

#### Vercel + Railway + Supabase

Vercel Hobby can host the personal, non-commercial Next.js frontend for $0, while the FastAPI/LangGraph process stays on Railway so SSE and durable work do not inherit Vercel Function duration limits.[^vercel-hobby][^vercel-functions] Railway's API service should fit near its $5 minimum under light use, although $5–10 is safer until measured.

Supabase Free makes this a roughly $5–10 demo stack, but Free has no managed daily backups; Supabase explicitly tells Free projects to perform and retain their own dumps.[^supabase-backups] For saved private Trips, Supabase Pro starts at $25/month and includes seven days of daily backups, making the credible split stack roughly $30–40 before any Vercel paid-plan requirement.[^supabase-pricing]

This option buys a stronger managed database/auth experience than Railway's database volume, but costs more and divides traces, configuration, CORS/auth failures, and outage diagnosis across three providers.

#### Render

Render currently lists Starter web/private/worker services at $7/month. A Next.js server plus FastAPI therefore costs $14/month; using Vercel Hobby or a truly static frontend can remove one of those services. Render PostgreSQL starts at $6/month for 256 MB and the next small tier is $19/month for 1 GB, producing a practical $20–33 range for the full topology.[^render-pricing]

Paid Render PostgreSQL receives continuous backups and PITR.[^render-backups] Free services are different: web services sleep after inactivity and Free PostgreSQL does not support backups.[^render-free] Use the free tier only for a seeded or disposable demonstration, not authoritative saved Trips.

#### Hetzner VPS

One small shared-resource Hetzner Cloud VM can run Caddy, Next.js, FastAPI, and PostgreSQL with Docker Compose. Current entry server prices plus optional IPv4, provider backups, and a small amount of independent backup storage make roughly EUR 6–14/month a defensible planning envelope; Hetzner bills servers hourly up to their monthly cap and prices server Backups at 20% of the server price.[^hetzner-cloud][^hetzner-billing]

This is likely the lowest cash-cost credible pilot, but not the lowest total-cost option for this project. The same developer debugging the agent would also own the host OS, firewall, TLS, containers, database upgrades, monitoring, capacity, and recovery. Provider VM snapshots also do not replace a tested off-site PostgreSQL logical backup.

### Recommendation for Flash Trips

Use two distinct answers to “cheapest”:

1. **Near-zero demonstration:** Vercel Hobby + Render Free API + Supabase Free, or entirely local Docker Compose. Use fixtures/seeded Trips, expect cold starts or pauses, export data manually, and do not describe it as a durable invitation service.
2. **Cheapest credible invitation pilot:** Railway Hobby with Next.js, FastAPI, and PostgreSQL in one project, budgeted at **$15–30/month until measured**, then tighten the budget from actual usage. Add scheduled volume snapshots and an encrypted off-platform `pg_dump`. This best matches the priority order of debuggability, maintainability, and controlled cost.

Choose Hetzner instead only if self-hosting and database operations are intentional learning objectives. Choose the Supabase Pro split stack when managed database recovery/auth is worth the extra ~$15–20/month. Choose Azure when Azure operational evidence, stronger managed recovery, or an employer-facing Azure deployment is itself a project goal—not because the application architecture requires Azure.

### Delivery decision should be target-neutral

The accepted CI principles remain valid, but the deployment target should not be frozen before the cost decision. Revise the delivery wording from “GitHub Actions → ACR → Container Apps” to:

```text
GitHub Actions CI
    -> build each OCI image once
    -> identify it by immutable digest
    -> deploy that digest automatically to test
    -> promote the same tested digest manually to production
```

Then implement a small provider-specific CD profile:

- Azure profile: ACR + Container Apps + Azure PostgreSQL;
- Railway profile: Railway services, using an immutable image/source revision and environment promotion;
- Render profile: Render services with the same commit/image identity;
- Hetzner profile: GHCR plus digest-pinned Docker Compose deployment.

This does not conflict with the capability-oriented modular-monolith ADR. It strengthens the existing decision that Azure is a deployment choice rather than an application dependency. Infrastructure code, secrets, health checks, migrations, smoke tests, and rollback commands are provider-specific; CI quality gates and build-once/promote-by-digest semantics are not.

## Sources

[^github-flow]: GitHub Docs, [GitHub flow](https://docs.github.com/en/get-started/using-github/github-flow).
[^github-environments]: GitHub Docs, [Managing environments for deployment](https://docs.github.com/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments).
[^github-concurrency]: GitHub Docs, [Control workflow concurrency](https://docs.github.com/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency).
[^vercel-hobby]: Vercel Docs, [Hobby plan](https://vercel.com/docs/plans/hobby).
[^vercel-functions]: Vercel Docs, [Vercel Functions limits](https://vercel.com/docs/functions/limitations).
[^supabase-pricing]: Supabase, [Pricing](https://supabase.com/pricing).
[^supabase-backups]: Supabase Docs, [Database backups](https://supabase.com/docs/guides/platform/backups).
[^upstash-pricing]: Upstash, [Redis pricing](https://upstash.com/pricing/redis).
[^railway-pricing]: Railway Docs, [Plans](https://docs.railway.com/pricing/plans).
[^railway-networking]: Railway Docs, [Public networking specs and limits](https://docs.railway.com/networking/public-networking/specs-and-limits).
[^railway-backups]: Railway Docs, [Backups](https://docs.railway.com/volumes/backups).
[^render-free]: Render Docs, [Deploy for free](https://render.com/docs/free).
[^render-backups]: Render Docs, [Postgres recovery and backups](https://render.com/docs/postgresql-backups).
[^hetzner-billing]: Hetzner Docs, [Cloud billing FAQ](https://docs.hetzner.com/cloud/billing/faq/).
[^azure-retail-api]: Microsoft Azure, [Retail Prices API](https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices/azure-retail-prices), queried for Azure Container Apps, Container Registry, and Azure Database for PostgreSQL in `westeurope` on 2026-08-19.
[^azure-container-apps-pricing]: Microsoft Azure, [Azure Container Apps pricing](https://azure.microsoft.com/en-us/pricing/details/container-apps/).
[^azure-postgres-backups]: Microsoft Learn, [Backup and restore in Azure Database for PostgreSQL flexible server](https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/concepts-backup-restore).
[^render-pricing]: Render, [Pricing](https://render.com/pricing).
[^hetzner-cloud]: Hetzner, [Cloud servers](https://www.hetzner.com/cloud/).
