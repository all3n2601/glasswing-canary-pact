import hashlib
import os
import secrets
import time

import pytest

URL = os.environ.get("CANARY_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="set CANARY_TEST_DATABASE_URL to run the Postgres storage tests")


@pytest.fixture
def pg(monkeypatch):
    import psycopg
    from psycopg import sql

    from canary_api import runtime, storage
    from canary_api.events import EventBus
    from canary_api.storage import PostgresStorage

    schema = f"canary_test_{secrets.token_hex(4)}"
    backend = PostgresStorage(URL, schema)  # type: ignore[arg-type]
    monkeypatch.setattr(storage, "_current", backend)
    monkeypatch.setattr(runtime, "bus", EventBus())
    monkeypatch.setattr(runtime, "_twin", None)
    try:
        yield schema, backend
    finally:
        backend.close()
        with psycopg.connect(URL, autocommit=True) as conn:  # type: ignore[arg-type]
            conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


def wait_for(client, run_id: str, status: str) -> None:
    deadline = time.monotonic() + 15
    while client.get(f"/runs/{run_id}").json()["status"] != status:
        assert time.monotonic() < deadline, f"{run_id} never reached {status}"
        time.sleep(0.05)


def test_postgres_backend_end_to_end(client, pg, monkeypatch) -> None:
    from api_auth_helpers import signup_and_login
    from real_data import sample_brief

    from canary_api import auth, runtime, storage
    from canary_api.events import EventBus
    from canary_api.storage import PostgresStorage

    schema, backend = pg
    assert auth.store().backend is backend

    viewer_token, viewer = signup_and_login(client, role="viewer")
    assert client.get("/auth/me", headers=viewer).json()["user_id"] == viewer_token["user"]["user_id"]
    duplicate = {"email": viewer_token["user"]["email"], "password": "another password", "display_name": "Dup"}
    assert client.post("/auth/signup", json=duplicate).status_code == 409
    assert client.post("/auth/logout", headers=viewer).status_code == 204
    assert client.get("/auth/me", headers=viewer).status_code == 401

    _, approver = signup_and_login(client, role="approver", display_name="Pg approver")
    run_id = client.post("/decisions", headers=approver,
                         json=sample_brief().model_dump(mode="json")).json()["run_id"]
    wait_for(client, run_id, "awaiting_approval")
    assert backend.load_active_twin() is not None
    package = client.get(f"/runs/{run_id}/package")
    package_hash = hashlib.sha256(package.content).hexdigest()
    decision = client.post(f"/runs/{run_id}/decision", headers=approver,
                           json={"decision": "approve", "decided_by": "x", "package_hash": package_hash})
    assert decision.status_code == 200
    wait_for(client, run_id, "completed")
    original = [e.model_dump(mode="json") for e in runtime.bus.runs[run_id].events]

    # A fresh process: every queued write lands, then a new pool and an empty in-memory bus read it back.
    runtime.bus.flush()
    restarted = PostgresStorage(URL, schema)  # type: ignore[arg-type]
    monkeypatch.setattr(storage, "_current", restarted)
    try:
        reloaded = EventBus().get(run_id)
        assert reloaded is not None and reloaded.state.status == "completed"
        assert [e.sequence for e in reloaded.events] == list(range(1, len(original) + 1))
        assert [e.model_dump(mode="json") for e in reloaded.events] == original
        assert reloaded.served_package_hash == package_hash
        assert reloaded.decision is not None and reloaded.decision.decided_by.startswith("Pg approver")
        assert auth.TokenSigner(auth._secret_bytes(), restarted).verify(viewer_token["access_token"]) is None
        assert restarted.user_by_email(viewer_token["user"]["email"]) is not None
        rows = restarted._run("SELECT count(*) FROM canary_decisions WHERE run_id = %s", (run_id,))
        assert rows == [(1,)]
    finally:
        restarted.close()


def test_postgres_tables_are_private(pg) -> None:
    from canary_api.storage import POSTGRES_TABLE_NAMES

    schema, backend = pg
    assert schema != "public"
    rows = backend._run("SELECT c.relname, c.relrowsecurity FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                        "WHERE n.nspname = %s AND c.relkind = 'r'", (schema,))
    security = dict(rows)
    assert set(POSTGRES_TABLE_NAMES) <= set(security)
    assert all(security[name] for name in POSTGRES_TABLE_NAMES)
    for role in ("anon", "authenticated"):
        if not backend._run("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,)):
            continue
        assert backend._run("SELECT has_schema_privilege(%s, %s, 'USAGE')", (role, schema)) == [(False,)]
        for name in POSTGRES_TABLE_NAMES:
            granted = backend._run(
                "SELECT has_table_privilege(%s, %s, 'SELECT') OR has_table_privilege(%s, %s, 'INSERT') "
                "OR has_table_privilege(%s, %s, 'UPDATE') OR has_table_privilege(%s, %s, 'DELETE')",
                (role, f"{schema}.{name}") * 4)
            assert granted == [(False,)], (role, name)
