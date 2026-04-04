"""
SQLite persistence layer for the authentication module.

Manages three tables:

* **users** — credentials, roles, lockout counters
* **refresh_tokens** — opaque token hashes with rotation chain
* **auth_events** — immutable audit log (login, logout, failures …)

The database uses WAL journal mode for concurrent-read performance and
applies incremental migrations on startup so that schema changes are
picked up automatically.
"""

from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class AuthDatabase:
    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()
        self._migrate()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_schema(self) -> None:
        with self.connection() as conn:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    username TEXT UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user',
                    is_active INTEGER NOT NULL DEFAULT 1,
                    is_verified INTEGER NOT NULL DEFAULT 0,
                    must_change_password INTEGER NOT NULL DEFAULT 0,
                    failed_login_attempts INTEGER NOT NULL DEFAULT 0,
                    lock_until INTEGER NOT NULL DEFAULT 0,
                    last_login_at INTEGER,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS refresh_tokens (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    token_hash TEXT NOT NULL UNIQUE,
                    expires_at INTEGER NOT NULL,
                    revoked_at INTEGER,
                    replaced_by_token_id TEXT,
                    ip_address TEXT,
                    user_agent TEXT,
                    created_at INTEGER NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS auth_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    email_hint TEXT,
                    event_type TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    ip_address TEXT,
                    user_agent TEXT,
                    detail TEXT,
                    created_at INTEGER NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
                );

                CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
                CREATE INDEX IF NOT EXISTS idx_refresh_user_id ON refresh_tokens(user_id);
                CREATE INDEX IF NOT EXISTS idx_refresh_token_hash ON refresh_tokens(token_hash);
                CREATE INDEX IF NOT EXISTS idx_refresh_expires_at ON refresh_tokens(expires_at);
                CREATE INDEX IF NOT EXISTS idx_auth_events_created_at ON auth_events(created_at);
                CREATE INDEX IF NOT EXISTS idx_auth_events_user_id ON auth_events(user_id);
                """
            )

    def _migrate(self) -> None:
        """Aplica migrações incrementais (colunas novas, etc.)."""
        with self.connection() as conn:
            columns = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
            if "must_change_password" not in columns:
                conn.execute("ALTER TABLE users ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0")

    def cleanup_expired_tokens(self, max_age_seconds: int = 86400 * 7) -> int:
        """Remove refresh tokens expirados ou revogados há mais de max_age_seconds.
        Retorna o número de tokens removidos."""
        cutoff = int(time.time()) - max_age_seconds
        with self.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM refresh_tokens WHERE (expires_at < ? AND expires_at > 0) OR (revoked_at IS NOT NULL AND revoked_at < ?)",
                (cutoff, cutoff),
            )
            return cursor.rowcount

    def cleanup_old_events(self, max_age_seconds: int = 86400 * 90) -> int:
        """Remove auth_events com mais de max_age_seconds (default 90 dias)."""
        cutoff = int(time.time()) - max_age_seconds
        with self.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM auth_events WHERE created_at < ?",
                (cutoff,),
            )
            return cursor.rowcount
