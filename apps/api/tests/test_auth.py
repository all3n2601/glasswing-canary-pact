import hashlib
import sqlite3
import time
import uuid
from datetime import timedelta

import pytest
from api_auth_helpers import signup_and_login

from canary_api import auth, runtime
from canary_api.stubs.twin import sample_brief
from contracts_py.api import AuthToken, UserPublic


def new_email() -> str:
    return f"user_{uuid.uuid4().hex[:8]}@example.com"


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def stored_hashes() -> list[str]:
    with sqlite3.connect(auth.store().path) as db:
        return [row[0] for row in db.execute("SELECT password_hash FROM users")]


def test_signup_login_me_logout(client) -> None:
    email, password = new_email(), "correct horse battery"
    created = client.post("/auth/signup", json={"email": email.upper(), "password": password, "display_name": "Ana"})
    assert created.status_code == 201
    user = UserPublic.model_validate(created.json())
    assert user.email == email and user.role == "viewer"
    assert "password" not in created.text

    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    token = AuthToken.model_validate(login.json())
    assert token.user == user and token.token_type == "bearer"

    assert UserPublic.model_validate(client.get("/auth/me", headers=bearer(token.access_token)).json()) == user
    assert client.post("/auth/logout", headers=bearer(token.access_token)).status_code == 204
    assert client.get("/auth/me", headers=bearer(token.access_token)).status_code == 401


def test_duplicate_signup_is_409(client) -> None:
    body = {"email": new_email(), "password": "long enough", "display_name": "Bo"}
    assert client.post("/auth/signup", json=body).status_code == 201
    assert client.post("/auth/signup", json=body | {"email": body["email"].upper()}).status_code == 409


def test_bad_signup_is_422(client) -> None:
    assert client.post("/auth/signup", json={"email": "nope", "password": "long enough", "display_name": "C"}).status_code == 422
    assert client.post("/auth/signup", json={"email": new_email(), "password": "short", "display_name": "C"}).status_code == 422


def test_wrong_password_and_unknown_email_look_the_same(client) -> None:
    email = new_email()
    client.post("/auth/signup", json={"email": email, "password": "the right one", "display_name": "D"})
    wrong = client.post("/auth/login", json={"email": email, "password": "the wrong one"})
    unknown = client.post("/auth/login", json={"email": new_email(), "password": "the right one"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_expired_tampered_and_missing_tokens_are_401(client) -> None:
    token, _ = signup_and_login(client, role="viewer")
    user = UserPublic.model_validate(token["user"])
    expired, _ = auth.signer().issue(user, lifetime=timedelta(seconds=-1))
    body, _, signature = token["access_token"].partition(".")
    forged_body = auth._b64encode(auth._b64decode(body).replace(b'"viewer"', b'"approver"'))
    other_key = auth.TokenSigner(b"not the server secret").issue(user)[0]
    for bad in (expired, f"{forged_body}.{signature}", f"{body}.{signature[:-2]}xx", other_key, "garbage", ""):
        assert client.get("/auth/me", headers=bearer(bad)).status_code == 401
    assert client.get("/auth/me").status_code == 401


def test_post_decisions_requires_a_token(client) -> None:
    assert client.post("/decisions", json=sample_brief().model_dump(mode="json")).status_code == 401


def await_package(client, headers: dict[str, str]) -> tuple[str, str]:
    run_id = client.post("/decisions?llm_mode=mock", headers=headers,
                         json=sample_brief().model_dump(mode="json")).json()["run_id"]
    deadline = time.monotonic() + 10
    while client.get(f"/runs/{run_id}").json()["status"] != "awaiting_approval":
        assert time.monotonic() < deadline
        time.sleep(0.02)
    package = client.get(f"/runs/{run_id}/package")
    return run_id, hashlib.sha256(package.content).hexdigest()


def test_viewer_is_403_and_approver_decides_as_themselves(client) -> None:
    _, viewer = signup_and_login(client, role="viewer")
    approver_token, approver = signup_and_login(client, role="approver", display_name="Priya")
    run_id, package_hash = await_package(client, viewer)
    body = {"decision": "approve", "decided_by": "someone else", "package_hash": package_hash}

    assert client.post(f"/runs/{run_id}/decision", json=body).status_code == 401
    assert client.post(f"/runs/{run_id}/decision", headers=viewer, json=body).status_code == 403
    response = client.post(f"/runs/{run_id}/decision", headers=approver, json=body)
    assert response.status_code == 200
    user_id = approver_token["user"]["user_id"]
    assert response.json()["decided_by"] == f"Priya ({user_id})"
    recorded = [e for e in runtime.bus.runs[run_id].events if e.type == "human_decision_recorded"]
    assert recorded[0].payload.decided_by == f"Priya ({user_id})" and recorded[0].actor == user_id


@pytest.mark.parametrize("path", ["/health", "/company", "/organization", "/organization/settings",
                                  "/organization/profile", "/departments", "/documents", "/replays"])
def test_read_endpoints_stay_open(client, path) -> None:
    assert client.get(path).status_code == 200


def test_replay_and_websocket_stay_open(client) -> None:
    run_id = client.post("/replays/sample_run/play?speed=4").json()["run_id"]
    with client.websocket_connect(f"/runs/{run_id}/events") as ws:
        assert ws.receive_json()["sequence"] == 1


def test_password_hashes_never_leave_the_server(client) -> None:
    token, headers = signup_and_login(client, role="approver")
    responses = [
        client.get("/auth/me", headers=headers).text,
        client.post("/auth/login", json={"email": token["user"]["email"], "password": "wrong password"}).text,
        str(token),
    ]
    hashes = stored_hashes()
    assert hashes and all(h.startswith("scrypt$16384$8$1$") for h in hashes)
    for text in responses:
        assert "scrypt$" not in text and "password_hash" not in text
        assert not any(h.split("$")[-1] in text for h in hashes)


def test_password_hashing_uses_salted_scrypt() -> None:
    first, second = auth.hash_password("same password"), auth.hash_password("same password")
    assert first != second
    assert auth.verify_password("same password", first) and not auth.verify_password("other password", first)


def test_demo_seed_creates_exactly_one_approver(monkeypatch) -> None:
    email = new_email()
    monkeypatch.setenv("CANARY_DEMO_APPROVER_EMAIL", email)
    monkeypatch.setenv("CANARY_DEMO_APPROVER_PASSWORD", "demo password 1")
    created = auth.seed_demo_approver()
    assert created is not None and created.role == "approver"
    assert auth.seed_demo_approver() is None
    with sqlite3.connect(auth.store().path) as db:
        rows = db.execute("SELECT role FROM users WHERE email = ?", (email,)).fetchall()
    assert rows == [("approver",)]


def test_demo_seed_needs_both_values(monkeypatch) -> None:
    monkeypatch.setenv("CANARY_DEMO_APPROVER_EMAIL", new_email())
    monkeypatch.delenv("CANARY_DEMO_APPROVER_PASSWORD", raising=False)
    assert auth.seed_demo_approver() is None
