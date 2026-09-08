import "server-only";

import {
  createCipheriv,
  createDecipheriv,
  createHmac,
  randomBytes,
  randomUUID,
  timingSafeEqual,
} from "node:crypto";

import { applicationSession } from "./session-policy";

export interface NewStoredSession {
  id: string;
  plannerId: string;
  identifierDigest: Uint8Array;
  csrfDigest: Uint8Array;
  accessTokenCiphertext: Uint8Array;
  accessTokenIv: Uint8Array;
  createdAt: Date;
  lastSeenAt: Date;
  idleExpiresAt: Date;
  absoluteExpiresAt: Date;
}

export interface StoredSession extends NewStoredSession {
  revokedAt: Date | null;
}

export interface SessionRepository {
  create(session: NewStoredSession): Promise<void>;
  find(identifierDigest: Uint8Array): Promise<StoredSession | null>;
  revoke(id: string, revokedAt: Date): Promise<void>;
  touch(id: string, lastSeenAt: Date, idleExpiresAt: Date): Promise<void>;
}

interface SessionManagerOptions {
  allowedOrigins: ReadonlySet<string>;
  clock?: () => Date;
  digestKey: Uint8Array;
  repository: SessionRepository;
  tokenEncryptionKey: Uint8Array;
}

interface AuthenticationInput {
  accessToken: string;
  plannerId: string;
  previousIdentifier?: string;
}

interface IssuedSession {
  cookieValue: string;
  csrfToken: string;
}

interface AuthorizationInput {
  cookieValue: string | undefined;
  csrfToken?: string;
  method: string;
  origin?: string;
}

export interface AuthorizedSession {
  accessToken: string;
  csrfToken: string;
  plannerId: string;
  sessionId: string;
}

const identifierPattern = /^[A-Za-z0-9_-]{43}$/;
const safeMethods = new Set(["GET", "HEAD", "OPTIONS"]);
const millisecondsPerSecond = 1_000;
const authTagBytes = 16;

function requireKey(key: Uint8Array, name: string): Buffer {
  if (key.byteLength !== 32) {
    throw new Error(`${name} must contain exactly 32 bytes`);
  }
  return Buffer.from(key);
}

function decodeOpaqueValue(value: string | undefined): Buffer | null {
  if (value === undefined || !identifierPattern.test(value)) {
    return null;
  }
  const decoded = Buffer.from(value, "base64url");
  return decoded.byteLength === 32 ? decoded : null;
}

export class ApplicationSessionManager {
  private readonly allowedOrigins: ReadonlySet<string>;
  private readonly clock: () => Date;
  private readonly digestKey: Buffer;
  private readonly repository: SessionRepository;
  private readonly tokenEncryptionKey: Buffer;

  constructor(options: SessionManagerOptions) {
    this.allowedOrigins = options.allowedOrigins;
    this.clock = options.clock ?? (() => new Date());
    this.digestKey = requireKey(options.digestKey, "Session digest key");
    this.repository = options.repository;
    this.tokenEncryptionKey = requireKey(
      options.tokenEncryptionKey,
      "Session token encryption key",
    );
  }

  async authenticate(input: AuthenticationInput): Promise<IssuedSession> {
    if (input.previousIdentifier !== undefined) {
      await this.revoke(input.previousIdentifier);
    }

    const identifier = randomBytes(32);
    const csrfToken = randomBytes(32);
    const now = this.clock();
    const absoluteExpiresAt = new Date(
      now.getTime() +
        applicationSession.absoluteLifetimeSeconds * millisecondsPerSecond,
    );
    const idleExpiresAt = new Date(
      now.getTime() +
        applicationSession.idleLifetimeSeconds * millisecondsPerSecond,
    );
    const identifierDigest = this.identifierDigest(identifier);
    const accessTokenIv = randomBytes(12);
    const cipher = createCipheriv(
      "aes-256-gcm",
      this.tokenEncryptionKey,
      accessTokenIv,
    );
    cipher.setAAD(identifierDigest);
    const encrypted = Buffer.concat([
      cipher.update(
        JSON.stringify({
          accessToken: input.accessToken,
          csrfToken: csrfToken.toString("base64url"),
        }),
        "utf8",
      ),
      cipher.final(),
      cipher.getAuthTag(),
    ]);

    await this.repository.create({
      id: randomUUID(),
      plannerId: input.plannerId,
      identifierDigest,
      csrfDigest: this.csrfDigest(identifier, csrfToken),
      accessTokenCiphertext: encrypted,
      accessTokenIv,
      createdAt: now,
      lastSeenAt: now,
      idleExpiresAt,
      absoluteExpiresAt,
    });

    return {
      cookieValue: identifier.toString("base64url"),
      csrfToken: csrfToken.toString("base64url"),
    };
  }

  async authorize(
    input: AuthorizationInput,
  ): Promise<AuthorizedSession | null> {
    const identifier = decodeOpaqueValue(input.cookieValue);
    if (identifier === null) {
      return null;
    }
    const session = await this.repository.find(
      this.identifierDigest(identifier),
    );
    const now = this.clock();
    if (
      session === null ||
      session.revokedAt !== null ||
      now >= session.idleExpiresAt ||
      now >= session.absoluteExpiresAt
    ) {
      return null;
    }

    if (!safeMethods.has(input.method.toUpperCase())) {
      if (
        input.origin === undefined ||
        !this.allowedOrigins.has(input.origin) ||
        !this.validCsrf(session, identifier, input.csrfToken)
      ) {
        return null;
      }
      const idleExpiresAt = new Date(
        Math.min(
          now.getTime() +
            applicationSession.idleLifetimeSeconds * millisecondsPerSecond,
          session.absoluteExpiresAt.getTime(),
        ),
      );
      await this.repository.touch(session.id, now, idleExpiresAt);
    }

    const encrypted = Buffer.from(session.accessTokenCiphertext);
    if (encrypted.byteLength <= authTagBytes) {
      return null;
    }
    const authTag = encrypted.subarray(encrypted.byteLength - authTagBytes);
    const ciphertext = encrypted.subarray(
      0,
      encrypted.byteLength - authTagBytes,
    );
    try {
      const decipher = createDecipheriv(
        "aes-256-gcm",
        this.tokenEncryptionKey,
        session.accessTokenIv,
      );
      decipher.setAAD(Buffer.from(session.identifierDigest));
      decipher.setAuthTag(authTag);
      const plaintext = Buffer.concat([
        decipher.update(ciphertext),
        decipher.final(),
      ]).toString("utf8");
      const payload: unknown = JSON.parse(plaintext);
      if (
        typeof payload !== "object" ||
        payload === null ||
        !("accessToken" in payload) ||
        typeof payload.accessToken !== "string" ||
        !("csrfToken" in payload) ||
        typeof payload.csrfToken !== "string"
      ) {
        return null;
      }
      return {
        accessToken: payload.accessToken,
        csrfToken: payload.csrfToken,
        plannerId: session.plannerId,
        sessionId: session.id,
      };
    } catch {
      return null;
    }
  }

  async revoke(cookieValue: string): Promise<void> {
    const identifier = decodeOpaqueValue(cookieValue);
    if (identifier === null) {
      return;
    }
    const session = await this.repository.find(
      this.identifierDigest(identifier),
    );
    if (session !== null && session.revokedAt === null) {
      await this.repository.revoke(session.id, this.clock());
    }
  }

  private identifierDigest(identifier: Uint8Array): Buffer {
    return createHmac("sha256", this.digestKey).update(identifier).digest();
  }

  private csrfDigest(identifier: Uint8Array, csrfToken: Uint8Array): Buffer {
    return createHmac("sha256", this.digestKey)
      .update(identifier)
      .update(csrfToken)
      .digest();
  }

  private validCsrf(
    session: StoredSession,
    identifier: Uint8Array,
    csrfValue: string | undefined,
  ): boolean {
    const csrfToken = decodeOpaqueValue(csrfValue);
    if (csrfToken === null) {
      return false;
    }
    const supplied = this.csrfDigest(identifier, csrfToken);
    const expected = Buffer.from(session.csrfDigest);
    return (
      expected.byteLength === supplied.byteLength &&
      timingSafeEqual(expected, supplied)
    );
  }
}
