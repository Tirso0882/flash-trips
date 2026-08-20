# Use Azure for the initial hosted deployment

Flash Trips will use Microsoft Azure for its initial hosted test and invitation-only production environments. The baseline deployment profile is GitHub Actions with OIDC, Bicep-managed infrastructure, Azure Container Registry, Azure Container Apps, Azure Database for PostgreSQL Flexible Server, Azure OpenAI behind the reasoning port, Key Vault and managed identities for secrets and access, and Azure Monitor/Application Insights for operational telemetry.

## Considered Options

- Railway was the recommended lower-cost managed alternative, but Azure was selected to provide a complete Microsoft-cloud implementation and stronger managed operational evidence.
- A Hetzner VM was cheaper in direct cash cost but would add host, network, TLS, database, backup, and recovery responsibilities to the same developer building the agentic system.
- Free-tier split hosting was rejected for saved private Trips because cold starts, inactivity pauses, fragmented diagnostics, and weak backup guarantees conflict with the invitation-only pilot.

## Consequences

CI remains deployment-target-neutral: it builds each OCI image once, validates it, and identifies it by immutable digest. The Azure CD profile promotes the same tested digest from test to production without rebuilding. Azure SDKs and resource schemas stay inside infrastructure and provider adapters; domain modules depend only on Flash Trips interfaces. “Full Azure stack” does not mean enabling Azure Managed Redis, Service Bus, Front Door, API Management, dedicated workers, or multiple application replicas before measured concurrency, reliability, security, or operational evidence justifies them.
