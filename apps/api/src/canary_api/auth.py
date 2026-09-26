import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from functools import cache
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import ValidationError

from contracts_py.api import AuthToken, LoginRequest, SignupRequest, UserPublic, UserRole

from canary_api.paths import runs_dir

log = logging.getLogger(__name__)

TOKEN_LIFETIME = timedelta(hours=12)
SCRYPT_N, SCRYPT_R, SCRYPT_P, SCRYPT_LEN = 2**14, 8, 1, 64
BAD_CREDENTIALS = "Invalid email or password"


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=SCRYPT_LEN)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    _, n, r, p, salt, expected = stored.split("$")
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p),
                            dklen=len(expected) // 2)
    return hmac.compare_digest(digest.hex(), expected)


# Checked against unknown emails so both login failures cost the same scrypt call.
_DUMMY_HASH = hash_password(secrets.token_hex(16))


class DuplicateEmail(ValueError):
    pass


class UserStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS users (user_id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, "
                "display_name TEXT NOT NULL, role TEXT NOT NULL, password_hash TEXT NOT NULL, created_at TEXT NOT NULL)"
            )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        return db

    @staticmethod
    def _public(row: sqlite3.Row) -> UserPublic:
        return UserPublic(user_id=row["user_id"], email=row["email"], display_name=row["display_name"],
                          role=row["role"], created_at=datetime.fromisoformat(row["created_at"]))

    def create(self, signup: SignupRequest) -> UserPublic:
        user = UserPublic(
            user_id=f"usr_{uuid.uuid4().hex[:16]}",
            email=signup.email.lower(),
            display_name=signup.display_name,
            role=signup.role,
            created_at=datetime.now(timezone.utc),
        )
        try:
            with self._connect() as db:
                db.execute(
                    "INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)",
                    (user.user_id, user.email, user.display_name, user.role.value, hash_password(signup.password),
                     user.created_at.isoformat()),
                )
        except sqlite3.IntegrityError as exc:
            raise DuplicateEmail(user.email) from exc
        return user

    def get(self, user_id: str) -> UserPublic | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return self._public(row) if row else None

    def exists(self, email: str) -> bool:
        with self._connect() as db:
            return db.execute("SELECT 1 FROM users WHERE email = ?", (email.lower(),)).fetchone() is not None

    def authenticate(self, email: str, password: str) -> UserPublic | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM users WHERE email = ?", (email.lower(),)).fetchone()
        if row is None:
            verify_password(password, _DUMMY_HASH)
            return None
        return self._public(row) if verify_password(password, row["password_hash"]) else None


class TokenSigner:
    def __init__(self, secret: bytes) -> None:
        self.secret = secret
        self.revoked: set[str] = set()

    def _sign(self, body: str) -> str:
        return _b64encode(hmac.new(self.secret, body.encode(), hashlib.sha256).digest())

    def issue(self, user: UserPublic, lifetime: timedelta = TOKEN_LIFETIME) -> tuple[str, datetime]:
        expires_at = datetime.now(timezone.utc) + lifetime
        claims = {"user_id": user.user_id, "role": user.role.value, "exp": int(expires_at.timestamp()),
                  "jti": secrets.token_hex(16)}
        body = _b64encode(json.dumps(claims, separators=(",", ":")).encode())
        return f"{body}.{self._sign(body)}", expires_at

    def verify(self, token: str) -> dict[str, Any] | None:
        body, _, signature = token.partition(".")
        if not body or not hmac.compare_digest(signature, self._sign(body)):
            return None
        try:
            claims = json.loads(_b64decode(body))
        except ValueError:
            return None
        if not isinstance(claims, dict) or claims.get("jti") in self.revoked:
            return None
        if not isinstance(claims.get("exp"), int) or claims["exp"] <= datetime.now(timezone.utc).timestamp():
            return None
        return claims

    def revoke(self, claims: dict[str, Any]) -> None:
        self.revoked.add(claims["jti"])


def _secret() -> bytes:
    configured = os.environ.get("CANARY_AUTH_SECRET")
    if configured:
        return configured.encode()
    log.warning("CANARY_AUTH_SECRET is not set; using a random secret, so tokens reset on restart")
    return secrets.token_bytes(32)


@cache
def store() -> UserStore:
    return UserStore(runs_dir() / "users.sqlite3")


@cache
def signer() -> TokenSigner:
    return TokenSigner(_secret())


def seed_demo_approver() -> UserPublic | None:
    email = os.environ.get("CANARY_DEMO_APPROVER_EMAIL")
    password = os.environ.get("CANARY_DEMO_APPROVER_PASSWORD")
    if not email or not password or store().exists(email):
        return None
    try:
        request = SignupRequest(email=email, password=password, display_name="Demo approver", role=UserRole.approver)
    except ValidationError:
        log.warning("CANARY_DEMO_APPROVER_EMAIL or CANARY_DEMO_APPROVER_PASSWORD is invalid; demo approver not created")
        return None
    user = store().create(request)
    log.info("created demo approver %s", user.user_id)
    return user


_bearer = HTTPBearer(auto_error=False)


def _unauthorized() -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated", headers={"WWW-Authenticate": "Bearer"})


def current_claims(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict[str, Any]:
    claims = signer().verify(credentials.credentials) if credentials else None
    if claims is None:
        raise _unauthorized()
    return claims


def current_user(claims: dict[str, Any] = Depends(current_claims)) -> UserPublic:
    user = store().get(str(claims.get("user_id")))
    if user is None:
        raise _unauthorized()
    return user


def require_approver(user: UserPublic = Depends(current_user)) -> UserPublic:
    if user.role is not UserRole.approver:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Approver role required")
    return user


router = APIRouter(prefix="/auth")


@router.post("/signup", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def signup(request: SignupRequest) -> UserPublic:
    try:
        return store().create(request)
    except DuplicateEmail as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered") from exc


@router.post("/login", response_model=AuthToken)
def login(request: LoginRequest) -> AuthToken:
    user = store().authenticate(request.email, request.password)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, BAD_CREDENTIALS)
    token, expires_at = signer().issue(user)
    return AuthToken(access_token=token, expires_at=expires_at, user=user)


@router.get("/me", response_model=UserPublic)
def me(user: UserPublic = Depends(current_user)) -> UserPublic:
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(claims: dict[str, Any] = Depends(current_claims)) -> Response:
    signer().revoke(claims)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
