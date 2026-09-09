import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";

test("a Planner completes the path from sign-in through Handbook download", async ({
  page,
}) => {
  const baseUrl = process.env.FLASH_TRIPS_JOURNEY_BASE_URL;
  expect(baseUrl, "the journey harness supplies its public URL").toBeTruthy();

  await page.goto(`${baseUrl}/planner`);
  const observedResponses: string[] = [];
  page.on("response", (response) => {
    observedResponses.push(`${response.status()} ${response.url()}`);
  });
  const callback = page.waitForResponse(
    (response) => new URL(response.url()).pathname === "/api/auth/callback",
    { timeout: 5_000 },
  );
  await page.getByRole("link", { name: "Continue with Google" }).click();
  const callbackResponse = await callback.catch(() => undefined);
  expect(callbackResponse, observedResponses.join("\n")).toBeDefined();
  expect(callbackResponse!.status()).toBe(307);
  await expect(page).toHaveURL(`${baseUrl}/planner`);
  await expect(
    page.getByRole("heading", { name: "Planner workspace" }),
  ).toBeVisible();

  await expect
    .poll(async () =>
      (await page.context().cookies()).find(
        (cookie) => cookie.name === "__Host-flash_trips_session",
      ),
    )
    .not.toBeUndefined();
  const cookies = await page.context().cookies();
  const resolvedSession = cookies.find(
    (cookie) => cookie.name === "__Host-flash_trips_session",
  );
  expect(resolvedSession?.value).toMatch(/^[A-Za-z0-9_-]{43}$/);

  const resolved = await page.request.get(`${baseUrl}/api/auth/session`);
  expect(resolved.status()).toBe(200);
  await expect(resolved.json()).resolves.toEqual({
    csrf_token: expect.stringMatching(/^[A-Za-z0-9_-]{43}$/),
  });

  await page.getByLabel("City").fill("Lisbon");
  await page.getByLabel("Start date").fill("2026-10-04");
  await page.getByLabel("End date").fill("2026-10-07");
  await page.getByLabel("Nights").fill("3");
  await page.getByRole("button", { name: "Create Trip" }).click();

  const savedTrips = page.getByRole("list", { name: "Saved Trips" });
  await expect(savedTrips).toContainText("Lisbon");
  const tripIdentifier = await savedTrips.locator("code").textContent();
  expect(tripIdentifier).toMatch(
    /^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/,
  );

  await page.getByRole("button", { name: "Start Run for Lisbon" }).click();
  await expect(
    page.getByRole("status", { name: "Run for Lisbon" }),
  ).toContainText("Succeeded");
  const planRevision = page.getByRole("region", { name: "Plan Revision 1" });
  await expect(planRevision).toContainText(
    "No fixture Travel Readiness concerns were found for Lisbon.",
  );
  const revisionIdentifier = await planRevision.locator("code").textContent();
  expect(revisionIdentifier).toMatch(
    /^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/,
  );

  const approvalRequest = page.getByRole("region", {
    name: "Approval Request for Plan Revision 1",
  });
  await expect(approvalRequest).toContainText(revisionIdentifier!);
  await page.getByRole("button", { name: "Approve Plan Revision 1" }).click();
  await expect(
    page.getByRole("status", { name: "Approval for Plan Revision 1" }),
  ).toContainText(revisionIdentifier!);

  const downloadStarted = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download Trip Handbook" }).click();
  const download = await downloadStarted;
  const downloadPath = await download.path();
  expect(downloadPath).not.toBeNull();
  const downloadedBytes = await readFile(downloadPath!);
  expect(downloadedBytes).toEqual(
    Buffer.from(
      '<!doctype html><html lang="en"><head><meta charset="utf-8">' +
        "<title>Trip Handbook, Plan Revision 1</title></head><body><main>" +
        `<h1>Trip Handbook</h1><p>Plan Revision 1: <code>${revisionIdentifier}</code></p>` +
        "<ul><li><p>No fixture Travel Readiness concerns were found for Lisbon.</p>" +
        "<p>Evidence: evaluation-fixture:travel-readiness-lisbon-v1, observed " +
        '<time datetime="2026-09-08T12:00:00+00:00">' +
        "2026-09-08T12:00:00+00:00</time></p></li></ul></main></body></html>",
    ),
  );
  const handbookIdentifier = await page
    .getByRole("status", { name: "Handbook for Plan Revision 1" })
    .locator("code")
    .textContent();
  expect(handbookIdentifier).toMatch(
    /^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/,
  );

  await page.reload();
  await expect(page.getByRole("list", { name: "Saved Trips" })).toContainText(
    tripIdentifier!,
  );
  await expect(
    page.getByRole("region", { name: "Plan Revision 1" }),
  ).toContainText(revisionIdentifier!);
  await expect(
    page.getByRole("status", { name: "Approval for Plan Revision 1" }),
  ).toContainText(revisionIdentifier!);
});
