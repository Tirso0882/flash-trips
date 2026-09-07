import { apiBaseUrl } from "./lib/server/config";

export function register(): void {
  if (process.env.NEXT_RUNTIME !== "nodejs") {
    return;
  }

  apiBaseUrl();
}
