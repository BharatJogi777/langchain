"""JWT authentication, role scopes, and service-level authorization.

Demo users are held in memory. Replace this repository with a persistent user
store or an OIDC provider before production deployment.
"""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import OAuth2PasswordBearer, SecurityScopes
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash

ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/token",
    scopes={
        "investigations:run": "Start an investigation",
        "investigations:read": "Read investigation results",
        "users:manage": "Manage user access",
    },
)
ISSUER = "devops-investigation-api"
AUDIENCE = "devops-investigation-clients"
ROLE_SCOPES = {
    "admin": {"investigations:run", "investigations:read", "users:manage"},
    "investigator": {"investigations:run", "investigations:read"},
    "viewer": {"investigations:read"},
}


@dataclass(frozen=True)
class UserRecord:
    username: str
    password_hash: str
    role: str
    allowed_services: frozenset[str]
    active: bool = True


@dataclass(frozen=True)
class Principal:
    subject: str
    role: str
    scopes: frozenset[str]
    allowed_services: frozenset[str]


@dataclass(frozen=True)
class SecuritySettings:
    secret_key: str
    users: dict[str, UserRecord]
    token_ttl_minutes: int = 20


class SecurityManager:
    def __init__(self, settings: SecuritySettings) -> None:
        if len(settings.secret_key) < 32:
            raise ValueError("JWT secret must contain at least 32 characters")
        if settings.token_ttl_minutes < 1:
            raise ValueError("token_ttl_minutes must be positive")
        self.settings = settings
        self.password_hash = PasswordHash.recommended()
        self._dummy_hash = self.password_hash.hash("not-a-real-user-password")

    def authenticate(self, username: str, password: str) -> UserRecord | None:
        user = self.settings.users.get(username)
        stored_hash = user.password_hash if user else self._dummy_hash
        valid = self.password_hash.verify(password, stored_hash)
        if not user or not valid or not user.active:
            return None
        return user

    def issue_token(self, user: UserRecord) -> str:
        now = datetime.now(timezone.utc)
        claims = {
            "sub": user.username,
            "iss": ISSUER,
            "aud": AUDIENCE,
            "iat": now,
            "nbf": now,
            "exp": now + timedelta(minutes=self.settings.token_ttl_minutes),
            "jti": uuid.uuid4().hex,
        }
        return jwt.encode(claims, self.settings.secret_key, algorithm=ALGORITHM)

    async def current_principal(
        self,
        security_scopes: SecurityScopes,
        token: Annotated[str, Depends(oauth2_scheme)],
    ) -> Principal:
        """Resolve the current identity and authorize OAuth2 scopes."""
        credentials_error = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )
        try:
            claims = jwt.decode(
                token,
                self.settings.secret_key,
                algorithms=[ALGORITHM],
                issuer=ISSUER,
                audience=AUDIENCE,
                options={"require": ["sub", "iss", "aud", "iat", "nbf", "exp", "jti"]},
            )
        except InvalidTokenError:
            raise credentials_error

        username = claims.get("sub")
        user = self.settings.users.get(username) if isinstance(username, str) else None
        if user is None or not user.active:
            raise credentials_error

        scopes = ROLE_SCOPES.get(user.role, set())
        missing = set(security_scopes.scopes) - scopes
        if missing:
            scope_value = " ".join(security_scopes.scopes)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
                headers={"WWW-Authenticate": f'Bearer scope="{scope_value}"'},
            )
        return Principal(
            subject=user.username,
            role=user.role,
            scopes=frozenset(scopes),
            allowed_services=user.allowed_services,
        )

    def require(self, *scopes: str):
        async def dependency(
            principal: Annotated[Principal, Security(self.current_principal, scopes=list(scopes))],
        ) -> Principal:
            return principal
        return dependency

    @staticmethod
    def authorize_service(principal: Principal, service: str) -> None:
        if "*" not in principal.allowed_services and service not in principal.allowed_services:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to investigate this service",
            )


def build_demo_security_from_environment() -> SecurityManager:
    """Create local demo identities from environment variables; never use defaults."""
    secret = os.environ.get("JWT_SECRET_KEY", "")
    passwords = {
        "admin": os.environ.get("DEMO_ADMIN_PASSWORD", ""),
        "investigator": os.environ.get("DEMO_INVESTIGATOR_PASSWORD", ""),
        "viewer": os.environ.get("DEMO_VIEWER_PASSWORD", ""),
    }
    if not secret or any(not value for value in passwords.values()):
        raise RuntimeError(
            "Set JWT_SECRET_KEY and DEMO_ADMIN_PASSWORD, "
            "DEMO_INVESTIGATOR_PASSWORD, DEMO_VIEWER_PASSWORD"
        )

    hasher = PasswordHash.recommended()
    users = {
        "admin": UserRecord("admin", hasher.hash(passwords["admin"]), "admin", frozenset({"*"})),
        "investigator": UserRecord(
            "investigator",
            hasher.hash(passwords["investigator"]),
            "investigator",
            frozenset({"checkout-api", "payments-api"}),
        ),
        "viewer": UserRecord(
            "viewer",
            hasher.hash(passwords["viewer"]),
            "viewer",
            frozenset({"checkout-api"}),
        ),
    }
    return SecurityManager(SecuritySettings(secret_key=secret, users=users))
