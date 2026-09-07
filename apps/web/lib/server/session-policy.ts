import "server-only";

export const applicationSession = Object.freeze({
  cookieName: "__Host-flash_trips_session",
  cookieOptions: Object.freeze({
    httpOnly: true,
    path: "/",
    sameSite: "strict" as const,
    secure: true,
  }),
});

export const originValidation = Object.freeze({
  allowedOriginsEnvironment: "FLASH_TRIPS_ALLOWED_ORIGINS",
  requestHeader: "origin",
  requiredForUnsafeMethods: true,
});

export const sessionBoundCsrf = Object.freeze({
  requestHeader: "x-flash-trips-csrf",
  requiredForUnsafeMethods: true,
  tokenSource: "server-side-session" as const,
});
