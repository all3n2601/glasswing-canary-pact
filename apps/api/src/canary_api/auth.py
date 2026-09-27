import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from functools import cache
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import ValidationError
from starlette.types import ASGIApp, Scope, Receive, Send
from starlette.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from contracts_py.api import AuthToken, LoginRequest, SignupRequest, UserPublic, UserRole

from canary_api import storage
from canary_api.paths import runs_dir
from canary_api.storage import DuplicateEmail, FileStorage, Storage

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


class UserStore:
    """Password hashing lives here; rows live in whichever storage backend is active."""

    def __init__(self, backend: Storage) -> None:
        self.backend = backend

    @property
    def path(self) -> Path | None:
        return self.backend.users_path if isinstance(self.backend, FileStorage) else None

    def create(self, signup: SignupRequest, role: UserRole = UserRole.viewer,
               organization_id: str | None = None) -> UserPublic:
        user = UserPublic(
            user_id=f"usr_{uuid.uuid4().hex[:16]}",
            email=signup.email.lower(),
            display_name=signup.display_name,
            role=role,
            created_at=datetime.now(timezone.utc),
        )
        self.backend.create_user(user, hash_password(signup.password), organization_id)
        return user

    def get(self, user_id: str) -> UserPublic | None:
        return self.backend.user_by_id(user_id)

    def exists(self, email: str) -> bool:
        return self.backend.user_by_email(email.lower()) is not None

    def authenticate(self, email: str, password: str) -> UserPublic | None:
        stored = self.backend.user_by_email(email.lower())
        if stored is None:
            verify_password(password, _DUMMY_HASH)
            return None
        return stored.user if verify_password(password, stored.password_hash) else None


class TokenSigner:
    def __init__(self, secret: bytes, backend: Storage | None = None) -> None:
        self.secret = secret
        self.backend = backend
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
        if not isinstance(claims, dict) or not isinstance(claims.get("jti"), str):
            return None
        if not isinstance(claims.get("exp"), int) or claims["exp"] <= datetime.now(timezone.utc).timestamp():
            return None
        if claims["jti"] in self.revoked or (self.backend is not None and self.backend.is_revoked(claims["jti"])):
            return None
        return claims

    def revoke(self, claims: dict[str, Any]) -> None:
        self.revoked.add(claims["jti"])
        if self.backend is not None:
            self.backend.revoke_token(claims["jti"], datetime.fromtimestamp(claims["exp"], timezone.utc))


def _secret() -> bytes:
    configured = os.environ.get("CANARY_AUTH_SECRET")
    if configured:
        return configured.encode()
    # Keep the local key across reloads and share it between workers. Publish a
    # fully written file atomically so concurrent starts never read a partial key.
    root = runs_dir()
    root.mkdir(parents=True, exist_ok=True)
    path = root / ".auth-secret"
    if not path.exists():
        with tempfile.NamedTemporaryFile(dir=root) as temporary:
            temporary.write(secrets.token_bytes(32))
            temporary.flush()
            try:
                os.link(temporary.name, path)
            except FileExistsError:
                pass
    secret = path.read_bytes()
    if len(secret) != 32:
        raise RuntimeError("Local auth key is invalid; restore it or configure CANARY_AUTH_SECRET")
    log.warning("CANARY_AUTH_SECRET is not set; using the persistent local key. "
                "Configure a shared secret for multi-host deployments.")
    return secret


def store() -> UserStore:
    return UserStore(storage.current())


@cache
def _secret_bytes() -> bytes:
    return _secret()


def signer() -> TokenSigner:
    backend = storage.current()
    if _signer.get("backend") is not backend:
        _signer.update(backend=backend, signer=TokenSigner(_secret_bytes(), backend))
    return _signer["signer"]


_signer: dict[str, Any] = {}


class OrganizationSessionMiddleware:
    """Bind HTTP and WebSocket work to server-owned account membership.

    Existing single-company demos retain their public read endpoints. As soon as
    a second organization exists, all company/run endpoints require a session.
    The client cannot choose its organization through request parameters.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        from canary_api import runtime

        public = scope.get("path", "") in {"/health", "/docs", "/openapi.json", "/redoc"} or scope.get("path", "").startswith("/auth/")
        if scope["type"] not in {"http", "websocket"} or public or scope.get("method") == "OPTIONS":
            await self.app(scope, receive, send)
            return

        def resolve() -> tuple[bool, str | None]:
            backend = storage.current()
            if len(backend.organization_ids()) < 2:
                return True, None
            header = dict(scope.get("headers", [])).get(b"authorization", b"").decode()
            scheme, _, token = header.partition(" ")
            claims = signer().verify(token) if scheme.lower() == "bearer" else None
            user = store().get(str(claims.get("user_id"))) if claims else None
            org_id = backend.user_organization(user.user_id) if user else None
            return bool(user and org_id), org_id

        allowed, org_id = await run_in_threadpool(resolve)
        if not allowed:
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 4401})
            else:
                await JSONResponse({"detail": "Not authenticated"}, status_code=401,
                                   headers={"WWW-Authenticate": "Bearer"})(scope, receive, send)
            return
        token = runtime.organization_scope.set(org_id)
        try:
            await self.app(scope, receive, send)
        finally:
            runtime.organization_scope.reset(token)


def seed_demo_approver() -> UserPublic | None:
    email = os.environ.get("CANARY_DEMO_APPROVER_EMAIL")
    password = os.environ.get("CANARY_DEMO_APPROVER_PASSWORD")
    if not email or not password or store().exists(email):
        return None
    try:
        request = SignupRequest(email=email, password=password, display_name="Demo approver")
    except ValidationError:
        log.warning("CANARY_DEMO_APPROVER_EMAIL or CANARY_DEMO_APPROVER_PASSWORD is invalid; demo approver not created")
        return None
    user = store().create(request, role=UserRole.approver)
    log.info("created demo approver %s", user.user_id)
    return user


def warn_if_no_approver() -> bool:
    if store().backend.has_role(UserRole.approver.value):
        return False
    log.warning("No approver account exists, so no decision can be approved. Set CANARY_DEMO_APPROVER_EMAIL and "
                "CANARY_DEMO_APPROVER_PASSWORD to create the demo approver at startup.")
    return True


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
def signup(body: dict[str, Any] = Body(...)) -> UserPublic:
    # Self-service accounts are always viewers; a client-supplied role is dropped, not honoured.
    body = {k: v for k, v in body.items() if k != "role"}
    try:
        request = SignupRequest.model_validate(body)
    except ValidationError as exc:
        raise HTTPException(422, exc.errors(include_url=False)) from exc
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
