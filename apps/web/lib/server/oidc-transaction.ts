import "server-only";

import {
  createCipheriv,
  createDecipheriv,
  hkdfSync,
  randomBytes,
} from "node:crypto";

import type { OidcTransaction } from "./oidc";

const lifetimeSeconds = 10 * 60;
const millisecondsPerSecond = 1_000;
const authenticationTagBytes = 16;

interface StoredTransaction extends OidcTransaction {
  expiresAt: number;
}

export const oidcTransactionCookie = Object.freeze({
  maxAge: lifetimeSeconds,
  name: "__Host-flash_trips_oidc",
  options: Object.freeze({
    httpOnly: true,
    maxAge: lifetimeSeconds,
    path: "/",
    sameSite: "lax" as const,
    secure: true,
  }),
});

function transactionKey(masterKey: Uint8Array): Buffer {
  if (masterKey.byteLength !== 32) {
    throw new Error(
      "OIDC transaction master key must contain exactly 32 bytes",
    );
  }
  return Buffer.from(
    hkdfSync(
      "sha256",
      masterKey,
      Buffer.alloc(0),
      "flash-trips-oidc-transaction-v1",
      32,
    ),
  );
}

export class OidcTransactionStore {
  private readonly clock: () => Date;
  private readonly key: Buffer;

  constructor(masterKey: Uint8Array, clock: () => Date = () => new Date()) {
    this.clock = clock;
    this.key = transactionKey(masterKey);
  }

  seal(transaction: OidcTransaction): string {
    const iv = randomBytes(12);
    const cipher = createCipheriv("aes-256-gcm", this.key, iv);
    const payload: StoredTransaction = {
      ...transaction,
      expiresAt:
        this.clock().getTime() + lifetimeSeconds * millisecondsPerSecond,
    };
    const ciphertext = Buffer.concat([
      cipher.update(JSON.stringify(payload), "utf8"),
      cipher.final(),
      cipher.getAuthTag(),
    ]);
    return `${iv.toString("base64url")}.${ciphertext.toString("base64url")}`;
  }

  open(value: string | undefined): OidcTransaction | null {
    if (value === undefined) {
      return null;
    }
    const parts = value.split(".");
    if (parts.length !== 2) {
      return null;
    }
    const [encodedIv, encodedCiphertext] = parts;
    if (encodedIv === undefined || encodedCiphertext === undefined) {
      return null;
    }
    try {
      const iv = Buffer.from(encodedIv, "base64url");
      const encrypted = Buffer.from(encodedCiphertext, "base64url");
      if (
        iv.byteLength !== 12 ||
        encrypted.byteLength <= authenticationTagBytes
      ) {
        return null;
      }
      const tag = encrypted.subarray(
        encrypted.byteLength - authenticationTagBytes,
      );
      const ciphertext = encrypted.subarray(
        0,
        encrypted.byteLength - authenticationTagBytes,
      );
      const decipher = createDecipheriv("aes-256-gcm", this.key, iv);
      decipher.setAuthTag(tag);
      const payload: unknown = JSON.parse(
        Buffer.concat([decipher.update(ciphertext), decipher.final()]).toString(
          "utf8",
        ),
      );
      if (
        typeof payload !== "object" ||
        payload === null ||
        !("codeVerifier" in payload) ||
        typeof payload.codeVerifier !== "string" ||
        !("nonce" in payload) ||
        typeof payload.nonce !== "string" ||
        !("state" in payload) ||
        typeof payload.state !== "string" ||
        !("expiresAt" in payload) ||
        typeof payload.expiresAt !== "number" ||
        this.clock().getTime() > payload.expiresAt
      ) {
        return null;
      }
      return {
        codeVerifier: payload.codeVerifier,
        nonce: payload.nonce,
        state: payload.state,
      };
    } catch {
      return null;
    }
  }
}
