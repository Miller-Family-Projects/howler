import base64
import os

import pytest

from howler_mcp.auth import AuthProvider


@pytest.mark.asyncio
async def test_passthrough_mode_forwards_the_caller_bearer_token():
    provider = AuthProvider(mode="passthrough")

    authorization = await provider.get_howler_authorization("caller-jwt")

    assert authorization == "Bearer caller-jwt"


@pytest.mark.asyncio
async def test_apikey_mode_uses_fixed_backend_identity_not_caller_token():
    provider = AuthProvider(
        mode="apikey",
        username="mara-readonly",
        api_key="mcp-read:secret-value",
    )

    authorization = await provider.get_howler_authorization("caller-jwt")

    encoded = base64.b64encode(b"mara-readonly:mcp-read:secret-value").decode("ascii")
    assert authorization == f"Basic {encoded}"
    assert "caller-jwt" not in authorization
    assert "secret-value" not in authorization


@pytest.mark.parametrize(
    ("username", "api_key"),
    [(None, "mcp-read:secret"), ("mara-readonly", None), ("", "key"), ("user", "")],
)
def test_apikey_mode_fails_closed_when_backend_credentials_are_incomplete(
    username: str | None, api_key: str | None
):
    with pytest.raises(ValueError, match="requires"):
        AuthProvider(mode="apikey", username=username, api_key=api_key)


def test_unknown_backend_auth_mode_fails_closed():
    with pytest.raises(ValueError, match="Unsupported"):
        AuthProvider(mode="oauth-magic")


@pytest.mark.asyncio
async def test_apikey_mode_reads_backend_secret_from_private_regular_file(tmp_path):
    secret_file = tmp_path / "backend-apikey"
    secret_file.write_text("mcp-read:file-secret\n")
    secret_file.chmod(0o600)
    provider = AuthProvider(
        mode="apikey",
        username="mara-readonly",
        api_key_file=str(secret_file),
    )

    authorization = await provider.get_howler_authorization("caller-jwt")

    encoded = base64.b64encode(b"mara-readonly:mcp-read:file-secret").decode("ascii")
    assert authorization == f"Basic {encoded}"


@pytest.mark.parametrize("mode", [0o644, 0o640])
def test_apikey_file_rejects_group_or_world_readable_permissions(tmp_path, mode):
    secret_file = tmp_path / "backend-apikey"
    secret_file.write_text("mcp-read:file-secret")
    secret_file.chmod(mode)

    with pytest.raises(ValueError, match="permissions"):
        AuthProvider(
            mode="apikey",
            username="mara-readonly",
            api_key_file=str(secret_file),
        )


def test_apikey_file_rejects_symlink(tmp_path):
    target = tmp_path / "target"
    target.write_text("mcp-read:file-secret")
    target.chmod(0o600)
    link = tmp_path / "backend-apikey"
    os.symlink(target, link)

    with pytest.raises(ValueError, match="regular file"):
        AuthProvider(
            mode="apikey",
            username="mara-readonly",
            api_key_file=str(link),
        )
