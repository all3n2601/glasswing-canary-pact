import logging
import time
from datetime import datetime, timezone

import pytest

from canary_api import auth, engine_port, storage
from canary_api.paths import DATA_DIR
from canary_api.events import EventBus
from canary_api.storage import FileStorage


@pytest.mark.parametrize(("url", "postgres"), [
    ("postgresql://user@host:5432/db", True),
    ("postgres://user@host/db", True),
    ("", False),
    ("postgresql+psycopg://user@host/db", False),
    ("sqlite:///x.db", False),
])
def test_backend_follows_database_url(monkeypatch, url, postgres) -> None:
    monkeypatch.setenv("DATABASE_URL", url)
    assert (storage.database_url() is not None) is postgres


def test_default_suite_uses_the_file_backend() -> None:
    assert isinstance(storage.current(), FileStorage)


def test_file_backend_reloads_runs_and_revocations_after_restart(client, tmp_path, monkeypatch) -> None:
    from api_auth_helpers import signup_and_login

    token, headers = signup_and_login(client, role="viewer")
    assert client.post("/auth/logout", headers=headers).status_code == 204
    restarted = FileStorage(storage.current().root)  # type: ignore[attr-defined]
    fresh = auth.TokenSigner(auth._secret_bytes(), restarted)
    assert fresh.verify(token["access_token"]) is None

    monkeypatch.setattr(storage, "_current", FileStorage(tmp_path))
    bus = EventBus()
    bus.create_run("run_restart", "dec_vendor_reduction", "stub-northstar-1")
    bus.flush()
    monkeypatch.setattr(storage, "_current", FileStorage(tmp_path))
    reloaded = EventBus().get("run_restart")
    assert reloaded is not None and reloaded.state.run_id == "run_restart"


def test_file_backend_rejects_duplicate_email(tmp_path) -> None:
    from contracts_py.api import UserPublic

    backend = FileStorage(tmp_path)
    user = UserPublic(user_id="usr_a", email="a@example.com", display_name="A", role="viewer",
                      created_at=datetime.now(timezone.utc))
    backend.create_user(user, "scrypt$x")
    with pytest.raises(storage.DuplicateEmail):
        backend.create_user(user.model_copy(update={"user_id": "usr_b"}), "scrypt$y")
    assert backend.user_by_id("usr_a") == user and backend.user_by_email("a@example.com").password_hash == "scrypt$x"


def test_file_backend_round_trips_the_active_company_twin(tmp_path) -> None:
    backend = FileStorage(tmp_path)
    twin = engine_port.load_twin(DATA_DIR / "synthetic_company.json")

    assert backend.load_active_twin() is None
    backend.save_twin(twin)
    assert backend.load_active_twin() == twin


class SlowFileStorage(FileStorage):
    def append_event(self, event) -> None:
        time.sleep(0.05)
        super().append_event(event)


def test_publish_does_not_wait_for_storage_and_keeps_order(tmp_path, monkeypatch) -> None:
    from contracts_py.events import AgentStarted, EventType

    monkeypatch.setattr(storage, "_current", SlowFileStorage(tmp_path))
    bus = EventBus()
    bus.create_run("run_slow", "dec_vendor_reduction", "stub-northstar-1")
    started = time.monotonic()
    for n in range(10):
        bus.publish("run_slow", EventType.agent_started, AgentStarted(agent_id=f"agent_{n}"), actor="test")
    assert time.monotonic() - started < 0.25, "publish waited on the slow backend"
    history = bus.runs["run_slow"].events
    assert [e.sequence for e in history] == list(range(1, 11))
    bus.flush()
    stored = storage.current().read_events("run_slow")
    assert [e.sequence for e in stored] == list(range(1, 11))
    assert [e.payload.agent_id for e in stored] == [f"agent_{n}" for n in range(10)]


def test_reload_reads_through_pending_writes(tmp_path, monkeypatch) -> None:
    from contracts_py.events import AgentStarted, EventType

    monkeypatch.setattr(storage, "_current", SlowFileStorage(tmp_path))
    bus = EventBus()
    bus.create_run("run_pending", "dec_vendor_reduction", "stub-northstar-1")
    for n in range(5):
        bus.publish("run_pending", EventType.agent_started, AgentStarted(agent_id=f"agent_{n}"), actor="test")
    reloaded = EventBus().get("run_pending")
    assert reloaded is not None and [e.sequence for e in reloaded.events] == [1, 2, 3, 4, 5]


def test_bus_follows_the_current_backend(tmp_path, monkeypatch) -> None:
    first, second = FileStorage(tmp_path / "a"), FileStorage(tmp_path / "b")
    bus = EventBus()
    monkeypatch.setattr(storage, "_current", first)
    assert bus.backend is first
    monkeypatch.setattr(storage, "_current", second)
    bus.create_run("run_switch", "dec_vendor_reduction", "stub-northstar-1")
    bus.flush()
    assert second.load_state("run_switch") is not None and first.load_state("run_switch") is None


def test_unreachable_database_falls_back_to_files(monkeypatch, caplog, tmp_path) -> None:
    secret = "pw_do_not_log"
    monkeypatch.setenv("DATABASE_URL", f"postgresql://canary:{secret}@127.0.0.1:1/canary")
    monkeypatch.setenv("CANARY_RUNS_DIR", str(tmp_path))
    monkeypatch.setattr(storage, "_current", None)
    monkeypatch.setattr(storage, "CONNECT_TIMEOUT_SECONDS", 2)
    with caplog.at_level(logging.WARNING, logger="canary_api.storage"):
        backend = storage.current()
    assert isinstance(backend, FileStorage) and backend.root == tmp_path
    assert "FALLING BACK" in caplog.text
    assert secret not in caplog.text and "127.0.0.1" not in caplog.text


def test_default_postgres_schema_is_not_public() -> None:
    assert storage.DEFAULT_SCHEMA == "canary"
