from unittest.mock import AsyncMock, Mock, patch

import pytest
from mcp.server.auth.provider import AccessToken

from howler_mcp.api import HowlerApiClient

FAKE_TOKEN = AccessToken(token="fake-bearer", client_id="test-client", scopes=[])


@pytest.mark.asyncio
async def test_call_reuses_and_closes_owned_http_client():
    http_client = Mock()
    http_client.request = AsyncMock()
    http_client.aclose = AsyncMock()
    http_client.request.return_value = Mock(
        json=Mock(return_value={"api_response": {"status": "ok"}})
    )
    auth_provider = Mock()
    auth_provider.get_howler_authorization = AsyncMock(
        return_value="Bearer howler-token"
    )

    with patch(
        "howler_mcp.api.httpx.AsyncClient", return_value=http_client
    ) as client_class:
        api_client = HowlerApiClient(auth_provider=auth_provider, timeout=2.0)
        first_response = await api_client.call(FAKE_TOKEN, "/whoami", "GET")
        second_response = await api_client.call(FAKE_TOKEN, "/whoami", "GET")
        await api_client.aclose()

    assert first_response == {"status": "ok"}
    assert second_response == {"status": "ok"}
    client_class.assert_called_once_with(timeout=2.0)
    assert http_client.request.await_count == 2
    for request_call in http_client.request.await_args_list:
        assert request_call.kwargs["headers"] == {
            "Authorization": "Bearer howler-token"
        }
    http_client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_call_reopens_owned_http_client_after_lifespan_close():
    first_client = Mock(is_closed=False)
    first_client.aclose = AsyncMock()
    second_client = Mock(is_closed=False)
    second_client.request = AsyncMock(
        return_value=Mock(
            raise_for_status=Mock(),
            json=Mock(return_value={"api_response": {"status": "reopened"}}),
        )
    )
    auth_provider = Mock()
    auth_provider.get_howler_authorization = AsyncMock(return_value="Basic bounded-key")

    with patch(
        "howler_mcp.api.httpx.AsyncClient",
        side_effect=[first_client, second_client],
    ) as client_class:
        api_client = HowlerApiClient(auth_provider=auth_provider, timeout=2.0)
        await api_client.aclose()
        first_client.is_closed = True
        response = await api_client.call(FAKE_TOKEN, "/whoami", "GET")

    assert response == {"status": "reopened"}
    assert client_class.call_count == 2
    second_client.request.assert_awaited_once()
