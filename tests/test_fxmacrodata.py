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
        "limit": 100,
        "offset": 0,
    }
    assert client.headers == {"X-API-Key": "test-key"}
    assert data["value"].tolist() == [1.10, 1.11]


@pytest.mark.asyncio
async def test_fetch_fxmacrodata_daily_omits_key_header_without_key() -> None:
    client = _FakeClient()

    await fetch_fxmacrodata_daily("EURUSD", "2026-01-01", "2026-01-04", client=client)

    assert client.headers == {}


class _PagedResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return self._payload


class _PagedClient:
    def __init__(self, total: int) -> None:
        self.rows = [
            {"date": f"2026-{1 + i // 28:02d}-{1 + i % 28:02d}", "val": 1 + i / 1000}
            for i in range(total)
        ][::-1]
        self.offsets: list[int] = []

    async def get(self, url: str, params: dict, headers: dict) -> _PagedResponse:
        offset = params["offset"]
        self.offsets.append(offset)
        page = self.rows[offset : offset + params["limit"]]
        more = offset + len(page) < len(self.rows)
        return _PagedResponse(
            {
                "data": page,
                "pagination": {"has_more": more, "next_offset": offset + len(page)},
            }
        )


@pytest.mark.asyncio
async def test_fetch_fxmacrodata_daily_reads_every_page() -> None:
    client = _PagedClient(total=250)

    data = await fetch_fxmacrodata_daily(
        "EURUSD", "2026-01-01", "2026-12-31", api_key="test-key", client=client
    )

    assert client.offsets == [0, 100, 200]
    assert len(data) == 250
    assert data["date"].is_monotonic_increasing


@pytest.mark.asyncio
async def test_fetch_fxmacrodata_daily_strips_and_rejects_bad_keys() -> None:
    client = _FakeClient()

    await fetch_fxmacrodata_daily(
        "EURUSD", "2026-01-01", "2026-01-04", api_key=" test-key\n", client=client
    )
    assert client.headers == {"X-API-Key": "test-key"}

    with pytest.raises(ValueError) as excinfo:
        await fetch_fxmacrodata_daily(
            "EURUSD",
            "2026-01-01",
            "2026-01-04",
            api_key="test-key\r\nX-Other: 1",
            client=_FakeClient(),
        )
    assert "test-key" not in str(excinfo.value)


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [{"detail": "Not Found"}, [], {"data": {}}])
async def test_fetch_fxmacrodata_daily_rejects_malformed_payload(
    payload: object,
) -> None:
    class _Client:
        async def get(self, url: str, params: dict, headers: dict) -> _PagedResponse:
            return _PagedResponse(payload)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="FXMacroData"):
        await fetch_fxmacrodata_daily(
            "EURUSD", "2026-01-01", "2026-01-04", api_key="test-key", client=_Client()
        )
