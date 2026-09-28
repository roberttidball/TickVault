from datetime import date

import pytest

from tick_vault.fxmacrodata import fetch_fxmacrodata_daily


class _FakeResponse:
    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return {
            "data": [
                {"date": "2026-01-03", "val": 1.11},
                {"date": "2026-01-02", "val": 1.10},
            ]
        }


class _FakeClient:
    def __init__(self) -> None:
        self.url = ""
        self.params = {}
        self.headers = {}

    async def get(self, url: str, params: dict, headers: dict) -> _FakeResponse:
        self.url = url
        self.params = params
        self.headers = headers
        return _FakeResponse()


@pytest.mark.asyncio
async def test_fetch_fxmacrodata_daily_builds_request_and_frame() -> None:
    client = _FakeClient()

    data = await fetch_fxmacrodata_daily(
        "EUR/USD",
        date(2026, 1, 1),
        "2026-01-04",
        api_key="test-key",
        client=client,
    )

    assert client.url == "https://api.fxmacrodata.com/v1/forex/eur/usd"
    assert client.params == {
        "start_date": "2026-01-01",
        "end_date": "2026-01-04",
    }
    assert client.headers == {"X-API-Key": "test-key"}
    assert data["value"].tolist() == [1.10, 1.11]


@pytest.mark.asyncio
async def test_fetch_fxmacrodata_daily_omits_key_header_without_key() -> None:
    client = _FakeClient()

    await fetch_fxmacrodata_daily("EURUSD", "2026-01-01", "2026-01-04", client=client)

    assert client.headers == {}
