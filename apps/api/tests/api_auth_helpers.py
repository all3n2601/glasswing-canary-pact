import uuid

_headers: dict[tuple[int, str], dict[str, str]] = {}


def signup_and_login(client, role: str = "approver", display_name: str = "Test user") -> tuple[dict, dict[str, str]]:
    email = f"{role}_{uuid.uuid4().hex[:8]}@example.com"
    password = f"pw-{uuid.uuid4().hex}"
    user = client.post("/auth/signup", json={"email": email, "password": password, "display_name": display_name,
                                             "role": role})
    assert user.status_code == 201, user.text
    token = client.post("/auth/login", json={"email": email, "password": password})
    assert token.status_code == 200, token.text
    return token.json(), {"Authorization": f"Bearer {token.json()['access_token']}"}


def auth_headers(client, role: str = "approver") -> dict[str, str]:
    key = (id(client), role)
    if key not in _headers:
        _headers[key] = signup_and_login(client, role)[1]
    return _headers[key]
