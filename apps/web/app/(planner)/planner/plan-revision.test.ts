import assert from "node:assert/strict";
import test from "node:test";

import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { PlanRevisionView, type PlanRevision } from "./plan-revision";

test("Plan Revision claims render hostile text as text, never markup", () => {
  const hostile = `<img src=x onerror="globalThis.compromised=true">`;
  const revision: PlanRevision = {
    base_revision_id: null,
    claims: [
      {
        evidence_reference: "fixture:hostile:v1",
        id: "01991e28-1d65-7000-8000-000000000004",
        kind: "travel_readiness",
        observed_at: "2026-09-08T12:00:00Z",
        text: hostile,
      },
    ],
    id: "01991e28-1d65-7000-8000-000000000003",
    revision_number: 1,
    run_id: "01991e28-1d65-7000-8000-000000000002",
    trip_id: "01991e28-1d65-7000-8000-000000000001",
  };

  const markup = renderToStaticMarkup(
    createElement(PlanRevisionView, { revision }),
  );

  assert.match(markup, /Plan Revision 1/);
  assert.match(markup, /01991e28-1d65-7000-8000-000000000003/);
  assert.doesNotMatch(markup, /<img/);
  assert.match(markup, /&lt;img src=x onerror=&quot;/);
});
