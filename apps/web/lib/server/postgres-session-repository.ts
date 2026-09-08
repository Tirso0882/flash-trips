import "server-only";

import type { Sql } from "postgres";

import type {
  NewStoredSession,
  SessionRepository,
  StoredSession,
} from "./session";

interface SessionRow {
  id: string;
  planner_id: string;
  identifier_digest: Buffer;
  csrf_digest: Buffer;
  access_token_ciphertext: Buffer;
  access_token_iv: Buffer;
  created_at: Date;
  last_seen_at: Date;
  idle_expires_at: Date;
  absolute_expires_at: Date;
  revoked_at: Date | null;
}

function toStoredSession(row: SessionRow): StoredSession {
  return {
    id: row.id,
    plannerId: row.planner_id,
    identifierDigest: row.identifier_digest,
    csrfDigest: row.csrf_digest,
    accessTokenCiphertext: row.access_token_ciphertext,
    accessTokenIv: row.access_token_iv,
    createdAt: row.created_at,
    lastSeenAt: row.last_seen_at,
    idleExpiresAt: row.idle_expires_at,
    absoluteExpiresAt: row.absolute_expires_at,
    revokedAt: row.revoked_at,
  };
}

export class PostgresSessionRepository implements SessionRepository {
  constructor(private readonly sql: Sql) {}

  async create(session: NewStoredSession): Promise<void> {
    await this.sql`
      INSERT INTO application_sessions (
        id,
        planner_id,
        identifier_digest,
        csrf_digest,
        access_token_ciphertext,
        access_token_iv,
        created_at,
        last_seen_at,
        idle_expires_at,
        absolute_expires_at
      )
      VALUES (
        ${session.id},
        ${session.plannerId},
        ${Buffer.from(session.identifierDigest)},
        ${Buffer.from(session.csrfDigest)},
        ${Buffer.from(session.accessTokenCiphertext)},
        ${Buffer.from(session.accessTokenIv)},
        ${session.createdAt},
        ${session.lastSeenAt},
        ${session.idleExpiresAt},
        ${session.absoluteExpiresAt}
      )
    `;
  }

  async find(identifierDigest: Uint8Array): Promise<StoredSession | null> {
    const rows = await this.sql<SessionRow[]>`
      SELECT
        id,
        planner_id,
        identifier_digest,
        csrf_digest,
        access_token_ciphertext,
        access_token_iv,
        created_at,
        last_seen_at,
        idle_expires_at,
        absolute_expires_at,
        revoked_at
      FROM application_sessions
      WHERE identifier_digest = ${Buffer.from(identifierDigest)}
    `;
    const row = rows[0];
    return row === undefined ? null : toStoredSession(row);
  }

  async revoke(id: string, revokedAt: Date): Promise<void> {
    await this.sql`
      UPDATE application_sessions
      SET revoked_at = ${revokedAt}
      WHERE id = ${id} AND revoked_at IS NULL
    `;
  }

  async touch(
    id: string,
    lastSeenAt: Date,
    idleExpiresAt: Date,
  ): Promise<void> {
    await this.sql`
      UPDATE application_sessions
      SET last_seen_at = ${lastSeenAt}, idle_expires_at = ${idleExpiresAt}
      WHERE id = ${id} AND revoked_at IS NULL
    `;
  }
}
