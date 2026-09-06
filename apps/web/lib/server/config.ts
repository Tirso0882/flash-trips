import "server-only";

const localApiBaseUrl = "http://127.0.0.1:8000";

export function apiBaseUrl(): string {
  const value = process.env.FLASH_TRIPS_API_BASE_URL;

  if (value === undefined) {
    if (process.env.NODE_ENV === "production") {
      throw new Error("FLASH_TRIPS_API_BASE_URL is required in production");
    }
    return localApiBaseUrl;
  }

  const url = new URL(value);
  const explicitlyAllowedInternalHttp =
    process.env.FLASH_TRIPS_ALLOW_INSECURE_INTERNAL_API === "true";
  const isLocalHttp =
    url.protocol === "http:" &&
    (url.hostname === "127.0.0.1" || url.hostname === "localhost");
  if (
    url.protocol !== "https:" &&
    !isLocalHttp &&
    !explicitlyAllowedInternalHttp
  ) {
    throw new Error(
      "FLASH_TRIPS_API_BASE_URL must use HTTPS outside local development",
    );
  }
  return url.origin;
}
