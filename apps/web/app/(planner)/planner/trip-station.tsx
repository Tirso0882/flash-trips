"use client";

import { FormEvent, useEffect, useState } from "react";

import { PlanRevisionView, type PlanRevision } from "./plan-revision";

// SKELETON_REPLACEMENT: issue 204 (FT-03) deepens this thin Trip station.
// SKELETON_REPLACEMENT: issue 216 (FT-14) deepens this thin Plan Revision station.
// SKELETON_REPLACEMENT: issue 200 (FT-21) deepens this thin Approval station.
// SKELETON_REPLACEMENT: issue 220 (FT-22) deepens this thin Handbook station.
// SKELETON_REPLACEMENT: issue 224 (FT-24) deepens this thin Handbook delivery.

interface TripStay {
  city: string;
  ends_on: string;
  nights: number;
  starts_on: string;
}

interface Trip {
  id: string;
  structure: {
    stays: TripStay[];
  };
}

interface TripList {
  items: Trip[];
}

interface Run {
  id: string;
  status: "Running" | "Succeeded" | "Blocked" | "Failed" | "Cancelled";
  terminal_outcome: {
    code: string;
    detail: string;
    status: "Succeeded" | "Blocked" | "Failed" | "Cancelled";
  } | null;
  trip_id: string;
}

interface Session {
  csrf_token: string;
}

interface ApprovalRequest {
  approval_id: string | null;
  id: string;
  plan_revision_id: string;
}

interface HandbookSnapshot {
  approval_id: string;
  checksum: string;
  format: "html";
  id: string;
  plan_revision_id: string;
}

function isSession(value: unknown): value is Session {
  return (
    typeof value === "object" &&
    value !== null &&
    "csrf_token" in value &&
    typeof value.csrf_token === "string"
  );
}

function isTripStay(value: unknown): value is TripStay {
  return (
    typeof value === "object" &&
    value !== null &&
    "city" in value &&
    typeof value.city === "string" &&
    "ends_on" in value &&
    typeof value.ends_on === "string" &&
    "nights" in value &&
    typeof value.nights === "number" &&
    "starts_on" in value &&
    typeof value.starts_on === "string"
  );
}

function isTrip(value: unknown): value is Trip {
  if (
    typeof value !== "object" ||
    value === null ||
    !("id" in value) ||
    typeof value.id !== "string" ||
    !("structure" in value) ||
    typeof value.structure !== "object" ||
    value.structure === null ||
    !("stays" in value.structure) ||
    !Array.isArray(value.structure.stays)
  ) {
    return false;
  }
  return value.structure.stays.every(isTripStay);
}

function isTripList(value: unknown): value is TripList {
  return (
    typeof value === "object" &&
    value !== null &&
    "items" in value &&
    Array.isArray(value.items) &&
    value.items.every(isTrip)
  );
}

const runStatuses = new Set([
  "Running",
  "Succeeded",
  "Blocked",
  "Failed",
  "Cancelled",
]);
const terminalRunStatuses = new Set([
  "Succeeded",
  "Blocked",
  "Failed",
  "Cancelled",
]);

function isRun(value: unknown): value is Run {
  if (
    typeof value !== "object" ||
    value === null ||
    !("id" in value) ||
    typeof value.id !== "string" ||
    !("trip_id" in value) ||
    typeof value.trip_id !== "string" ||
    !("status" in value) ||
    typeof value.status !== "string" ||
    !runStatuses.has(value.status) ||
    !("terminal_outcome" in value)
  ) {
    return false;
  }
  const outcome = value.terminal_outcome;
  return (
    outcome === null ||
    (typeof outcome === "object" &&
      "status" in outcome &&
      typeof outcome.status === "string" &&
      terminalRunStatuses.has(outcome.status) &&
      "code" in outcome &&
      typeof outcome.code === "string" &&
      "detail" in outcome &&
      typeof outcome.detail === "string")
  );
}

function isPlanRevision(value: unknown): value is PlanRevision {
  return (
    typeof value === "object" &&
    value !== null &&
    "id" in value &&
    typeof value.id === "string" &&
    "trip_id" in value &&
    typeof value.trip_id === "string" &&
    "run_id" in value &&
    typeof value.run_id === "string" &&
    "base_revision_id" in value &&
    (value.base_revision_id === null ||
      typeof value.base_revision_id === "string") &&
    "revision_number" in value &&
    typeof value.revision_number === "number" &&
    "claims" in value &&
    Array.isArray(value.claims) &&
    value.claims.every(
      (claim) =>
        typeof claim === "object" &&
        claim !== null &&
        "id" in claim &&
        typeof claim.id === "string" &&
        "kind" in claim &&
        claim.kind === "travel_readiness" &&
        "text" in claim &&
        typeof claim.text === "string" &&
        "evidence_reference" in claim &&
        typeof claim.evidence_reference === "string" &&
        "observed_at" in claim &&
        typeof claim.observed_at === "string",
    )
  );
}

function isApprovalRequest(value: unknown): value is ApprovalRequest {
  return (
    typeof value === "object" &&
    value !== null &&
    "id" in value &&
    typeof value.id === "string" &&
    "plan_revision_id" in value &&
    typeof value.plan_revision_id === "string" &&
    "approval_id" in value &&
    (value.approval_id === null || typeof value.approval_id === "string")
  );
}

function isHandbookSnapshot(value: unknown): value is HandbookSnapshot {
  return (
    typeof value === "object" &&
    value !== null &&
    "id" in value &&
    typeof value.id === "string" &&
    "plan_revision_id" in value &&
    typeof value.plan_revision_id === "string" &&
    "approval_id" in value &&
    typeof value.approval_id === "string" &&
    "format" in value &&
    value.format === "html" &&
    "checksum" in value &&
    typeof value.checksum === "string"
  );
}

async function loadCurrentPlanRevision(
  tripId: string,
): Promise<PlanRevision | null> {
  const response = await fetch(`/api/trips/${tripId}/plan-revision`, {
    cache: "no-store",
  });
  if (!response.ok) return null;
  const revision: unknown = await response.json();
  return isPlanRevision(revision) ? revision : null;
}

async function loadCurrentApprovalRequest(
  tripId: string,
): Promise<ApprovalRequest | null> {
  const response = await fetch(`/api/trips/${tripId}/approval-request`, {
    cache: "no-store",
  });
  if (!response.ok) return null;
  const request: unknown = await response.json();
  return isApprovalRequest(request) ? request : null;
}

export default function TripStation() {
  const [approvalRequests, setApprovalRequests] = useState<
    Record<string, ApprovalRequest>
  >({});
  const [csrfToken, setCsrfToken] = useState("");
  const [error, setError] = useState("");
  const [handbooks, setHandbooks] = useState<Record<string, HandbookSnapshot>>(
    {},
  );
  const [runs, setRuns] = useState<Record<string, Run>>({});
  const [planRevisions, setPlanRevisions] = useState<
    Record<string, PlanRevision>
  >({});
  const [trips, setTrips] = useState<Trip[]>([]);

  useEffect(() => {
    async function load(): Promise<void> {
      const [sessionResponse, tripsResponse] = await Promise.all([
        fetch("/api/auth/session", { cache: "no-store" }),
        fetch("/api/trips", { cache: "no-store" }),
      ]);
      if (!sessionResponse.ok || !tripsResponse.ok) {
        setError("Sign in to create and reopen private Trips.");
        return;
      }
      const session: unknown = await sessionResponse.json();
      const list: unknown = await tripsResponse.json();
      if (!isSession(session) || !isTripList(list)) {
        setError("The session or Trip list response was invalid.");
        return;
      }
      setCsrfToken(session.csrf_token);
      setTrips(list.items);
      const revisions = await Promise.all(
        list.items.map((trip) => loadCurrentPlanRevision(trip.id)),
      );
      setPlanRevisions(
        Object.fromEntries(
          revisions
            .filter((revision) => revision !== null)
            .map((revision) => [revision.trip_id, revision]),
        ),
      );
      const requests = await Promise.all(
        list.items.map((trip) => loadCurrentApprovalRequest(trip.id)),
      );
      setApprovalRequests(
        Object.fromEntries(
          requests
            .filter((request) => request !== null)
            .map((request) => [request.plan_revision_id, request]),
        ),
      );
    }

    void load();
  }, []);

  async function create(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setError("");
    const form = event.currentTarget;
    const data = new FormData(form);
    const response = await fetch("/api/trips", {
      body: JSON.stringify({
        city: data.get("city"),
        ends_on: data.get("ends_on"),
        nights: Number(data.get("nights")),
        starts_on: data.get("starts_on"),
      }),
      headers: {
        "content-type": "application/json",
        "x-flash-trips-csrf": csrfToken,
      },
      method: "POST",
    });
    if (!response.ok) {
      setError("The Trip could not be created.");
      return;
    }
    const trip: unknown = await response.json();
    if (!isTrip(trip)) {
      setError("The created Trip response was invalid.");
      return;
    }
    setTrips((current) => [...current, trip]);
    form.reset();
  }

  async function startRun(trip: Trip): Promise<void> {
    setError("");
    const started = await fetch(`/api/trips/${trip.id}/runs`, {
      headers: { "x-flash-trips-csrf": csrfToken },
      method: "POST",
    });
    if (!started.ok) {
      setError("The Run could not be started.");
      return;
    }
    const accepted: unknown = await started.json();
    if (!isRun(accepted)) {
      setError("The Run response was invalid.");
      return;
    }
    const observed = await fetch(`/api/runs/${accepted.id}`, {
      cache: "no-store",
    });
    if (!observed.ok) {
      setError("The Run status could not be read.");
      return;
    }
    const run: unknown = await observed.json();
    if (!isRun(run)) {
      setError("The Run status response was invalid.");
      return;
    }
    setRuns((current) => ({ ...current, [trip.id]: run }));
    if (run.status === "Succeeded") {
      const revision = await loadCurrentPlanRevision(trip.id);
      if (revision === null) {
        setError("The current Plan Revision response was invalid.");
        return;
      }
      setPlanRevisions((current) => ({ ...current, [trip.id]: revision }));
      const request = await loadCurrentApprovalRequest(trip.id);
      if (request === null) {
        setError("The Approval Request response was invalid.");
        return;
      }
      setApprovalRequests((current) => ({
        ...current,
        [revision.id]: request,
      }));
    }
  }

  async function approve(request: ApprovalRequest): Promise<void> {
    setError("");
    const response = await fetch("/api/approvals", {
      body: JSON.stringify({
        approval_request_id: request.id,
        plan_revision_id: request.plan_revision_id,
      }),
      headers: {
        "content-type": "application/json",
        "x-flash-trips-csrf": csrfToken,
      },
      method: "POST",
    });
    if (!response.ok) {
      setError("The Plan Revision could not be approved.");
      return;
    }
    const approval: unknown = await response.json();
    if (
      typeof approval !== "object" ||
      approval === null ||
      !("id" in approval) ||
      typeof approval.id !== "string"
    ) {
      setError("The Approval response was invalid.");
      return;
    }
    const approvalId = approval.id;
    setApprovalRequests((current) => ({
      ...current,
      [request.plan_revision_id]: {
        ...request,
        approval_id: approvalId,
      },
    }));
  }

  async function downloadHandbook(
    trip: Trip,
    revision: PlanRevision,
  ): Promise<void> {
    setError("");
    const response = await fetch(`/api/trips/${trip.id}/handbook-snapshot`, {
      headers: { "x-flash-trips-csrf": csrfToken },
      method: "POST",
    });
    if (!response.ok) {
      setError("The Trip Handbook could not be compiled.");
      return;
    }
    const value: unknown = await response.json();
    if (!isHandbookSnapshot(value)) {
      setError("The Handbook Snapshot response was invalid.");
      return;
    }
    setHandbooks((current) => ({ ...current, [revision.id]: value }));
    const link = document.createElement("a");
    link.href = `/api/handbook-snapshots/${value.id}/export`;
    link.download = `flash-trips-${value.id}.html`;
    document.body.append(link);
    link.click();
    link.remove();
  }

  return (
    <section aria-labelledby="trips-heading">
      <h2 id="trips-heading">Your Trips</h2>
      <p>
        Dates and destinations are private Sensitive Trip Data. They are saved
        only to plan and reopen this Trip.
      </p>
      <form onSubmit={create}>
        <label>
          City
          <input name="city" required />
        </label>
        <label>
          Start date
          <input name="starts_on" required type="date" />
        </label>
        <label>
          End date
          <input name="ends_on" required type="date" />
        </label>
        <label>
          Nights
          <input min="0" name="nights" required type="number" />
        </label>
        <button disabled={csrfToken.length === 0} type="submit">
          Create Trip
        </button>
      </form>
      {error.length > 0 ? <p role="alert">{error}</p> : null}
      {trips.length === 0 ? (
        <p>No Trips yet.</p>
      ) : (
        <ul aria-label="Saved Trips">
          {trips.map((trip) => {
            const stay = trip.structure.stays[0];
            const planRevision = planRevisions[trip.id];
            const approvalRequest =
              planRevision === undefined
                ? undefined
                : approvalRequests[planRevision.id];
            return (
              <li key={trip.id}>
                <strong>{stay?.city}</strong>{" "}
                <span>
                  {stay?.starts_on} to {stay?.ends_on}, {stay?.nights} nights
                </span>
                <br />
                <code>{trip.id}</code>
                <br />
                <button
                  disabled={csrfToken.length === 0}
                  onClick={() => void startRun(trip)}
                  type="button"
                >
                  Start Run for {stay?.city}
                </button>
                {runs[trip.id] !== undefined ? (
                  <p aria-label={`Run for ${stay?.city}`} role="status">
                    Run: {runs[trip.id]?.status}
                  </p>
                ) : null}
                {planRevision !== undefined ? (
                  <PlanRevisionView revision={planRevision} />
                ) : null}
                {planRevision !== undefined && approvalRequest !== undefined ? (
                  <section
                    aria-label={`Approval Request for Plan Revision ${planRevision.revision_number}`}
                  >
                    <h3>
                      Approval Request for Plan Revision{" "}
                      {planRevision.revision_number}
                    </h3>
                    <p>
                      Request: <code>{approvalRequest.id}</code>
                    </p>
                    <p>
                      Exact revision:{" "}
                      <code>{approvalRequest.plan_revision_id}</code>
                    </p>
                    {approvalRequest.approval_id === null ? (
                      <button
                        disabled={csrfToken.length === 0}
                        onClick={() => void approve(approvalRequest)}
                        type="button"
                      >
                        Approve Plan Revision {planRevision.revision_number}
                      </button>
                    ) : (
                      <>
                        <p
                          aria-label={`Approval for Plan Revision ${planRevision.revision_number}`}
                          role="status"
                        >
                          Approval recorded for revision{" "}
                          <code>{approvalRequest.plan_revision_id}</code>
                        </p>
                        <button
                          disabled={csrfToken.length === 0}
                          onClick={() =>
                            void downloadHandbook(trip, planRevision)
                          }
                          type="button"
                        >
                          Download Trip Handbook
                        </button>
                        {handbooks[planRevision.id] !== undefined ? (
                          <p
                            aria-label={`Handbook for Plan Revision ${planRevision.revision_number}`}
                            role="status"
                          >
                            Handbook Snapshot{" "}
                            <code>{handbooks[planRevision.id]?.id}</code>
                          </p>
                        ) : null}
                      </>
                    )}
                  </section>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
