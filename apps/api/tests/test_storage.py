from datetime import datetime, timezone

import pytest

from canary_api import auth, storage
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


def test_file_backend_reloads_runs_and_revocations_after_restart(client, tmp_path) -> None:
    from api_auth_helpers import signup_and_login

    token, headers = signup_and_login(client, role="viewer")
    assert client.post("/auth/logout", headers=headers).status_code == 204
    restarted = FileStorage(storage.current().root)  # type: ignore[attr-defined]
    fresh = auth.TokenSigner(auth._secret_bytes(), restarted)
    assert fresh.verify(token["access_token"]) is None

    backend = FileStorage(tmp_path)
    bus = EventBus(backend)
    bus.create_run("run_restart", "dec_vendor_reduction", "stub-northstar-1")
    reloaded = EventBus(FileStorage(tmp_path)).get("run_restart")
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
