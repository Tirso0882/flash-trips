"use client";

import { FormEvent, useEffect, useState } from "react";

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

export default function TripStation() {
  const [csrfToken, setCsrfToken] = useState("");
  const [error, setError] = useState("");
  const [runs, setRuns] = useState<Record<string, Run>>({});
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
      const session = (await sessionResponse.json()) as Session;
      const list = (await tripsResponse.json()) as TripList;
      setCsrfToken(session.csrf_token);
      setTrips(list.items);
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
    const trip = (await response.json()) as Trip;
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
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
