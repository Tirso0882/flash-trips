import {
  expect,
  test,
  type APIRequestContext,
  type Page,
} from "@playwright/test";
import { spawnSync } from "node:child_process";

const resourceId = "01991e28-1d65-7000-8000-000000000099";

type UnusableState = "revoked" | "idle-expired" | "absolute-expired";

async function signIn(page: Page, baseUrl: string): Promise<string> {
  await page.goto(`${baseUrl}/planner`);
  await page.getByRole("link", { name: "Continue with Google" }).click();
  await expect(page).toHaveURL(`${baseUrl}/planner`);
  await expect
    .poll(async () =>
      (await page.context().cookies()).find(
        (cookie) => cookie.name === "__Host-flash_trips_session",
      ),
    )
    .not.toBeUndefined();
  const session = await page.request.get(`${baseUrl}/api/auth/session`);
  expect(session.status()).toBe(200);
  return ((await session.json()) as { csrf_token: string }).csrf_token;
}

function makeSessionUnusable(state: UnusableState): void {
  const container = process.env.FLASH_TRIPS_JOURNEY_POSTGRES_CONTAINER;
  expect(container, "the journey harness supplies its database").toBeTruthy();
  const assignment = {
    revoked: "revoked_at = now()",
    "idle-expired":
      "created_at = created_at - interval '1 day', " +
      "last_seen_at = created_at - interval '1 day', " +
      "idle_expires_at = now() - interval '1 second'",
    "absolute-expired":
      "created_at = created_at - interval '8 days', " +
      "last_seen_at = now(), idle_expires_at = now() + interval '1 day', " +
      "absolute_expires_at = now() - interval '1 second'",
  }[state];
  const result = spawnSync(
    "docker",
    [
      "exec",
      container!,
      "psql",
      "-U",
      "postgres",
      "-d",
      "flash_trips",
      "-c",
      `UPDATE application_sessions SET ${assignment} WHERE revoked_at IS NULL`,
    ],
    { encoding: "utf8" },
  );
  expect(result.status, result.stdout + result.stderr).toBe(0);
}

async function protectedActions(
  request: APIRequestContext,
  baseUrl: string,
  csrfToken: string,
) {
  const mutation = {
    headers: { origin: baseUrl, "x-flash-trips-csrf": csrfToken },
  };
  return [
    ["Trip read", await request.get(`${baseUrl}/api/trips/${resourceId}`)],
    ["Trip list", await request.get(`${baseUrl}/api/trips`)],
    [
      "Run start",
      await request.post(`${baseUrl}/api/trips/${resourceId}/runs`, mutation),
    ],
    ["Run read", await request.get(`${baseUrl}/api/runs/${resourceId}`)],
    [
      "Plan Revision read",
      await request.get(`${baseUrl}/api/trips/${resourceId}/plan-revision`),
    ],
    [
      "Approval action",
      await request.post(`${baseUrl}/api/approvals`, {
        ...mutation,
        data: {
          approval_request_id: resourceId,
          plan_revision_id: resourceId,
        },
      }),
    ],
    [
      "Handbook download",
      await request.get(
        `${baseUrl}/api/handbook-snapshots/${resourceId}/export`,
      ),
    ],
  ] as const;
}

for (const state of ["revoked", "idle-expired", "absolute-expired"] as const) {
  test(`${state} application session is refused by every BFF station`, async ({
    page,
  }) => {
    const baseUrl = process.env.FLASH_TRIPS_JOURNEY_BASE_URL;
    expect(baseUrl, "the journey harness supplies its public URL").toBeTruthy();
    const csrfToken = await signIn(page, baseUrl!);
    makeSessionUnusable(state);

    for (const [station, response] of await protectedActions(
      page.request,
      baseUrl!,
      csrfToken,
    )) {
      expect(response.status(), station).toBe(401);
      await expect(response.json()).resolves.toMatchObject({
        code: "authentication_required",
      });
    }
  });
}
