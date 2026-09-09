export interface PlanClaim {
  evidence_reference: string;
  id: string;
  kind: "travel_readiness";
  observed_at: string;
  text: string;
}

export interface PlanRevision {
  base_revision_id: string | null;
  claims: PlanClaim[];
  id: string;
  revision_number: number;
  run_id: string;
  trip_id: string;
}

interface PlanRevisionViewProperties {
  revision: PlanRevision;
}

export function PlanRevisionView({ revision }: PlanRevisionViewProperties) {
  return (
    <section aria-label={`Plan Revision ${revision.revision_number}`}>
      <h3>Plan Revision {revision.revision_number}</h3>
      <p>
        Visible revision: <code>{revision.id}</code>
      </p>
      <ul aria-label="Plan claims">
        {revision.claims.map((claim) => (
          <li key={claim.id}>
            <p>{claim.text}</p>
            <small>
              Evidence: {claim.evidence_reference}, observed{" "}
              <time dateTime={claim.observed_at}>{claim.observed_at}</time>
            </small>
          </li>
        ))}
      </ul>
    </section>
  );
}
