import base64
import logging
import stat
from pathlib import Path
from typing import Any

import jwt
from jwt import PyJWKClient
from mcp.server.auth.provider import AccessToken, TokenVerifier

from .config import HOWLER_API

logger = logging.getLogger(__name__)


class KeycloakTokenVerifier(TokenVerifier):
    def __init__(self, issuer: str, jwks_uri: str, audience: str, required_scope: str):
        self.issuer = issuer
        self.audience = audience
        self.required_scope = required_scope
        self.jwks_client = PyJWKClient(jwks_uri)

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            signing_key = self.jwks_client.get_signing_key_from_jwt(token)

            claims: dict[str, Any] = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256", "RS384", "RS512", "PS256", "PS384", "PS512"],
                issuer=self.issuer,
                options={
                    "require": ["exp", "iat", "iss"],
                    "verify_aud": False,
                },
            )

            if not self._audience_matches(claims):
                logger.warning(
                    "TOKEN REJECTED: audience mismatch. EXPECTED AUD: %s, ACTUAL AUD: %s",
                    self.audience,
                    claims.get("aud"),
                )
                return None

            scopes = self._extract_scopes(claims)

            if self.required_scope not in scopes:
                logger.warning(
                    "TOKEN REJECTED: missing required scope. REQUIRED SCOPE: %s, TOKEN SCOPES: %s",
                    self.required_scope,
                    scopes,
                )
                return None

            expires_at = claims.get("exp")
            if not isinstance(expires_at, int):
                logger.warning("TOKEN REJECTED: exp missing or invalid")
                return None

            client_id = self._extract_client_id(claims)

            return AccessToken(
                token=token,
                client_id=client_id,
                scopes=scopes,
                expires_at=expires_at,
                resource=self.audience,
            )

        except Exception:
            logger.exception("TOKEN REJECTED: Exception during verification.")
            return None

    def _audience_matches(self, claims: dict[str, Any]) -> bool:
        aud = claims.get("aud")

        if isinstance(aud, str):
            return aud == self.audience

        if isinstance(aud, list):
            return self.audience in aud

        return False

    def _extract_scopes(self, claims: dict[str, Any]) -> list[str]:
        scope_value = claims.get("scope", claims.get("scp", ""))
        if isinstance(scope_value, str) and scope_value.strip():
            return scope_value.strip().split()
        return []

    def _extract_client_id(self, claims: dict[str, Any]) -> str:
        azp = claims.get("azp")
        if isinstance(azp, str) and azp:
            return azp

        client_id = claims.get("client_id")
        if isinstance(client_id, str) and client_id:
            return client_id

        return "unknown-client"


class AuthProvider:
    """Build the authorization header used for Howler backend requests."""

    def __init__(
        self,
        mode: str = HOWLER_API.AUTH_MODE,
        username: str | None = HOWLER_API.USERNAME,
        api_key: str | None = None,
        api_key_file: str | None = HOWLER_API.API_KEY_FILE,
    ) -> None:
        self.mode = mode.strip().lower()
        if self.mode not in {"passthrough", "apikey"}:
            raise ValueError(f"Unsupported Howler backend auth mode: {mode}")
        if api_key and api_key_file:
            raise ValueError("Howler backend API key has multiple sources")
        if api_key_file:
            path = Path(api_key_file)
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode):
                raise ValueError("Howler backend API key must be a regular file")
            if stat.S_IMODE(info.st_mode) & 0o077:
                raise ValueError(
                    "Howler backend API key file permissions are too broad"
                )
            api_key = path.read_text().strip()
        if self.mode == "apikey" and (not username or not api_key):
            raise ValueError(
                "Howler backend auth mode 'apikey' requires username and API key"
            )
        self.username = username
        self.api_key = api_key

    async def get_howler_authorization(self, user_token: str) -> str:
        if self.mode == "passthrough":
            return f"Bearer {user_token}"

        credential = f"{self.username}:{self.api_key}".encode()
        encoded = base64.b64encode(credential).decode("ascii")
        return f"Basic {encoded}"

    async def get_howler_token(self, user_token: str) -> str:
        """Backward-compatible pass-through helper."""
        return user_token
