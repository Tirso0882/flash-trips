import { expect, test } from "@playwright/test";

import { otherPlannerTripId } from "./harness.mts";

test("a Planner is denied at the first station of another Planner's journey", async ({
  page,
}) => {
  const baseUrl = process.env.FLASH_TRIPS_JOURNEY_BASE_URL;
  expect(baseUrl, "the journey harness supplies its public URL").toBeTruthy();

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

  const refused = await page.request.get(
    `${baseUrl}/api/trips/${otherPlannerTripId}`,
  );

  expect(refused.status()).toBe(404);
  await expect(refused.json()).resolves.toMatchObject({
    code: "trip_not_found",
    detail: "The Trip was not found.",
  });
});
