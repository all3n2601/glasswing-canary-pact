"""Persistence for runs, users and revoked tokens: files and SQLite by default, Postgres when DATABASE_URL says so."""

import json
import logging
import os
import re
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from contracts_py.api import UserPublic
from contracts_py.events import Event, RunState
from contracts_py.package import DecisionPackage, HumanDecision

log = logging.getLogger(__name__)

SCHEMA_NAME = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")


class DuplicateEmail(ValueError):
    pass


@dataclass
class StoredUser:
    user: UserPublic
    password_hash: str


class Storage(Protocol):
    def append_event(self, event: Event) -> None: ...

    def read_events(self, run_id: str) -> list[Event]: ...

    def save_state(self, state: RunState) -> None: ...

    def load_state(self, run_id: str) -> RunState | None: ...

    def save_package(self, run_id: str, package: DecisionPackage, package_hash: str) -> None: ...

    def load_package(self, run_id: str) -> tuple[DecisionPackage, str] | None: ...

    def save_decision(self, decision: HumanDecision) -> None: ...

    def create_user(self, user: UserPublic, password_hash: str) -> None: ...

    def user_by_email(self, email: str) -> StoredUser | None: ...

    def user_by_id(self, user_id: str) -> UserPublic | None: ...

    def revoke_token(self, token_id: str, expires_at: datetime) -> None: ...

    def is_revoked(self, token_id: str) -> bool: ...

    def close(self) -> None: ...


def _user(user_id: str, email: str, display_name: str, role: str, created_at: Any) -> UserPublic:
    created = created_at if isinstance(created_at, datetime) else datetime.fromisoformat(created_at)
    return UserPublic(user_id=user_id, email=email, display_name=display_name, role=role, created_at=created)  # type: ignore[arg-type]


class FileStorage:
    """Run events and state as files under the runs directory; users and revoked tokens in SQLite."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.users_path = root / "users.sqlite3"
        self._packages: dict[str, tuple[DecisionPackage, str]] = {}
        root.mkdir(parents=True, exist_ok=True)
        with self._users() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS users (user_id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, "
                "display_name TEXT NOT NULL, role TEXT NOT NULL, password_hash TEXT NOT NULL, created_at TEXT NOT NULL)"
            )
            db.execute("CREATE TABLE IF NOT EXISTS revoked_tokens (token_id TEXT PRIMARY KEY, expires_at TEXT NOT NULL)")

    def _users(self) -> sqlite3.Connection:
        return sqlite3.connect(self.users_path)

    def _dir(self, run_id: str) -> Path:
        return self.root / run_id

    def append_event(self, event: Event) -> None:
        with (self._dir(event.run_id) / "events.jsonl").open("a") as handle:
            handle.write(event.model_dump_json() + "\n")

    def read_events(self, run_id: str) -> list[Event]:
        path = self._dir(run_id) / "events.jsonl"
        if not path.is_file():
            return []
        return [Event.model_validate(json.loads(line)) for line in path.read_text().splitlines() if line.strip()]

    def save_state(self, state: RunState) -> None:
        directory = self._dir(state.run_id)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "state.json").write_text(state.model_dump_json(indent=2))

    def load_state(self, run_id: str) -> RunState | None:
        path = self._dir(run_id) / "state.json"
        return RunState.model_validate_json(path.read_text()) if path.is_file() else None

    # The file backend keeps the served package in memory, as before; the decision itself is in events.jsonl.
    def save_package(self, run_id: str, package: DecisionPackage, package_hash: str) -> None:
        self._packages[run_id] = (package, package_hash)

    def load_package(self, run_id: str) -> tuple[DecisionPackage, str] | None:
        return self._packages.get(run_id)

    def save_decision(self, decision: HumanDecision) -> None:
        pass

    def create_user(self, user: UserPublic, password_hash: str) -> None:
        try:
            with self._users() as db:
                db.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)",
                           (user.user_id, user.email, user.display_name, user.role.value, password_hash,
                            user.created_at.isoformat()))
        except sqlite3.IntegrityError as exc:
            raise DuplicateEmail(user.email) from exc

    def user_by_email(self, email: str) -> StoredUser | None:
        with self._users() as db:
            row = db.execute("SELECT user_id, email, display_name, role, created_at, password_hash FROM users "
                             "WHERE email = ?", (email,)).fetchone()
        return StoredUser(_user(*row[:5]), row[5]) if row else None

    def user_by_id(self, user_id: str) -> UserPublic | None:
        with self._users() as db:
            row = db.execute("SELECT user_id, email, display_name, role, created_at FROM users WHERE user_id = ?",
                             (user_id,)).fetchone()
        return _user(*row) if row else None

    def revoke_token(self, token_id: str, expires_at: datetime) -> None:
        with self._users() as db:
            db.execute("INSERT OR IGNORE INTO revoked_tokens VALUES (?, ?)", (token_id, expires_at.isoformat()))

    def is_revoked(self, token_id: str) -> bool:
        with self._users() as db:
            return db.execute("SELECT 1 FROM revoked_tokens WHERE token_id = ?", (token_id,)).fetchone() is not None

    def close(self) -> None:
        pass


POSTGRES_TABLES = [
    "CREATE TABLE IF NOT EXISTS canary_runs (run_id TEXT PRIMARY KEY, state JSONB NOT NULL, "
    "updated_at TIMESTAMPTZ NOT NULL DEFAULT now())",
    "CREATE TABLE IF NOT EXISTS canary_events (run_id TEXT NOT NULL, sequence INTEGER NOT NULL, type TEXT NOT NULL, "
    "event JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now(), PRIMARY KEY (run_id, sequence))",
    "CREATE TABLE IF NOT EXISTS canary_packages (run_id TEXT PRIMARY KEY, package JSONB NOT NULL, "
    "package_hash TEXT NOT NULL, served_at TIMESTAMPTZ NOT NULL DEFAULT now())",
    "CREATE TABLE IF NOT EXISTS canary_decisions (id BIGSERIAL PRIMARY KEY, run_id TEXT NOT NULL, "
    "package_id TEXT NOT NULL, decision JSONB NOT NULL, decided_at TIMESTAMPTZ NOT NULL)",
    "CREATE TABLE IF NOT EXISTS canary_users (user_id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, "
    "display_name TEXT NOT NULL, role TEXT NOT NULL, password_hash TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL)",
    "CREATE TABLE IF NOT EXISTS canary_revoked_tokens (token_id TEXT PRIMARY KEY, expires_at TIMESTAMPTZ NOT NULL)",
]


class PostgresStorage:
    def __init__(self, url: str, schema: str = "public") -> None:
        from psycopg import sql
        from psycopg_pool import ConnectionPool

        if not SCHEMA_NAME.fullmatch(schema):
            raise ValueError("CANARY_DB_SCHEMA must be a lowercase SQL identifier")
        self.schema = schema
        search_path = sql.SQL("SET search_path TO {}").format(sql.Identifier(schema))

        def configure(conn: Any) -> None:
            conn.execute(search_path)
            conn.commit()

        # Poolers such as Supabase's cap connections, so the pool stays small; prepared statements stay off
        # so a transaction-mode pooler also works.
        self.pool = ConnectionPool(url, min_size=1, max_size=4, configure=configure, open=False,
                                   kwargs={"prepare_threshold": None}, name="canary")
        with self._bootstrap(url) as conn:
            conn.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(schema)))
            conn.execute(search_path)
            for statement in POSTGRES_TABLES:
                conn.execute(statement)  # type: ignore[arg-type]
        self.pool.open(wait=True)
        log.info("postgres storage ready (schema %s)", schema)

    @staticmethod
    def _bootstrap(url: str) -> Any:
        import psycopg

        return psycopg.connect(url, autocommit=True, prepare_threshold=None)

    def _run(self, query: str, params: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
        with self.pool.connection() as conn:
            cursor = conn.execute(query, params)  # type: ignore[arg-type]
            return cursor.fetchall() if cursor.description else []

    def append_event(self, event: Event) -> None:
        from psycopg.types.json import Jsonb

        self._run("INSERT INTO canary_events (run_id, sequence, type, event) VALUES (%s, %s, %s, %s)",
                  (event.run_id, event.sequence, event.type.value, Jsonb(event.model_dump(mode="json"))))

    def read_events(self, run_id: str) -> list[Event]:
        rows = self._run("SELECT event FROM canary_events WHERE run_id = %s ORDER BY sequence", (run_id,))
        return [Event.model_validate(row[0]) for row in rows]

    def save_state(self, state: RunState) -> None:
        from psycopg.types.json import Jsonb

        self._run("INSERT INTO canary_runs (run_id, state, updated_at) VALUES (%s, %s, now()) "
                  "ON CONFLICT (run_id) DO UPDATE SET state = EXCLUDED.state, updated_at = now()",
                  (state.run_id, Jsonb(state.model_dump(mode="json"))))

    def load_state(self, run_id: str) -> RunState | None:
        rows = self._run("SELECT state FROM canary_runs WHERE run_id = %s", (run_id,))
        return RunState.model_validate(rows[0][0]) if rows else None

    def save_package(self, run_id: str, package: DecisionPackage, package_hash: str) -> None:
        from psycopg.types.json import Jsonb

        self._run("INSERT INTO canary_packages (run_id, package, package_hash) VALUES (%s, %s, %s) "
                  "ON CONFLICT (run_id) DO UPDATE SET package = EXCLUDED.package, "
                  "package_hash = EXCLUDED.package_hash, served_at = now()",
                  (run_id, Jsonb(package.model_dump(mode="json")), package_hash))

    def load_package(self, run_id: str) -> tuple[DecisionPackage, str] | None:
        rows = self._run("SELECT package, package_hash FROM canary_packages WHERE run_id = %s", (run_id,))
        return (DecisionPackage.model_validate(rows[0][0]), rows[0][1]) if rows else None

    def save_decision(self, decision: HumanDecision) -> None:
        from psycopg.types.json import Jsonb

        self._run("INSERT INTO canary_decisions (run_id, package_id, decision, decided_at) VALUES (%s, %s, %s, %s)",
                  (decision.run_id, decision.package_id, Jsonb(decision.model_dump(mode="json")), decision.decided_at))

    def create_user(self, user: UserPublic, password_hash: str) -> None:
        from psycopg.errors import UniqueViolation

        try:
            self._run("INSERT INTO canary_users VALUES (%s, %s, %s, %s, %s, %s)",
                      (user.user_id, user.email, user.display_name, user.role.value, password_hash, user.created_at))
        except UniqueViolation as exc:
            raise DuplicateEmail(user.email) from exc

    def user_by_email(self, email: str) -> StoredUser | None:
        rows = self._run("SELECT user_id, email, display_name, role, created_at, password_hash FROM canary_users "
                         "WHERE email = %s", (email,))
        return StoredUser(_user(*rows[0][:5]), rows[0][5]) if rows else None

    def user_by_id(self, user_id: str) -> UserPublic | None:
        rows = self._run("SELECT user_id, email, display_name, role, created_at FROM canary_users WHERE user_id = %s",
                         (user_id,))
        return _user(*rows[0]) if rows else None

    def revoke_token(self, token_id: str, expires_at: datetime) -> None:
        self._run("INSERT INTO canary_revoked_tokens VALUES (%s, %s) ON CONFLICT (token_id) DO NOTHING",
                  (token_id, expires_at))

    def is_revoked(self, token_id: str) -> bool:
        return bool(self._run("SELECT 1 FROM canary_revoked_tokens WHERE token_id = %s", (token_id,)))

    def close(self) -> None:
        self.pool.close()


def database_url() -> str | None:
    url = os.environ.get("DATABASE_URL", "")
    return url if url.startswith(("postgres://", "postgresql://")) else None


_lock = threading.Lock()
_current: Storage | None = None


def current() -> Storage:
    global _current
    with _lock:
        if _current is None:
            url = database_url()
            if url:
                _current = PostgresStorage(url, os.environ.get("CANARY_DB_SCHEMA") or "public")
            else:
                from canary_api.paths import runs_dir

                _current = FileStorage(runs_dir())
        return _current


def close() -> None:
    global _current
    with _lock:
        if _current is not None:
            _current.close()
            _current = None
