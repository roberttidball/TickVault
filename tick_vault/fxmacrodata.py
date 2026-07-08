"""FXMacroData daily reference-rate helpers."""

from datetime import date, datetime
from typing import Any

import pandas as pd
from httpx import AsyncClient

from .constants import FXMACRODATA_API_BASE


def _split_pair(symbol: str) -> tuple[str, str]:
    clean_symbol = symbol.replace("/", "").replace("-", "").upper()
    if len(clean_symbol) != 6:
        raise ValueError(
            "FXMacroData symbols must be six-letter FX pairs, for example EURUSD"
        )
    return clean_symbol[:3], clean_symbol[3:]


def _format_date(value: date | datetime | str) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def _daily_rows_to_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=["date", "value"])

    data = pd.DataFrame(rows)
    data["date"] = pd.to_datetime(data["date"])
    data["value"] = data["val"].astype(float)
    return data[["date", "value"]].sort_values("date").reset_index(drop=True)


async def fetch_fxmacrodata_daily(
    symbol: str,
    start: date | datetime | str,
    end: date | datetime | str,
    *,
    api_key: str | None = None,
    client: AsyncClient | None = None,
    base_url: str = FXMACRODATA_API_BASE,
) -> pd.DataFrame:
    """
    Fetch daily FXMacroData spot reference rates for a currency pair.

    TickVault stores high-resolution Dukascopy tick data.  This helper provides
    an optional daily reference series that can be used to compare tick-derived
    bars with FXMacroData's official/reference spot history.

    Args:
        symbol: Currency pair such as ``"EURUSD"`` or ``"EUR/USD"``.
        start: Start date in ``YYYY-MM-DD`` form, or a date/datetime object.
        end: End date in ``YYYY-MM-DD`` form, or a date/datetime object.
        api_key: Optional FXMacroData Professional API key.
        client: Optional ``httpx.AsyncClient`` to reuse connection pools.
        base_url: FXMacroData REST API base URL.

    Returns:
        A pandas DataFrame with ``date`` and ``value`` columns.
    """
    base, quote = _split_pair(symbol)
    close_client = client is None
    if client is None:
        client = AsyncClient(timeout=30.0)

    params = {"start_date": _format_date(start), "end_date": _format_date(end)}
    if api_key:
        params["api_key"] = api_key

    try:
        response = await client.get(
            f"{base_url.rstrip('/')}/forex/{base.lower()}/{quote.lower()}",
            params=params,
        )
        response.raise_for_status()
        return _daily_rows_to_frame(response.json().get("data", []))
    finally:
        if close_client:
            await client.aclose()
