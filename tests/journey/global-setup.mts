import { startJourneyHarness } from "./harness.mts";

export default async function globalSetup(): Promise<() => Promise<void>> {
  const harness = await startJourneyHarness();
  process.env.FLASH_TRIPS_JOURNEY_BASE_URL = harness.baseUrl;
  return harness.stop;
}
