from __future__ import annotations

from abc import ABC, abstractmethod
from time import perf_counter
from typing import Any

import requests

from valutatrade_hub.core.exceptions import ApiRequestError


class BaseApiClient(ABC):
    @abstractmethod
    def fetch_rates(self) -> tuple[dict[str, float], dict[str, Any]]:
        """
        Returns:
          rates: {"BTC_USD": 59337.21, ...}
          meta:  diagnostics (status_code, request_ms, etc.)
        """
        raise NotImplementedError


class CoinGeckoClient(BaseApiClient):
    def __init__(self, crypto_id_map: dict[str, str], vs_currency: str, timeout: int = 10) -> None:
        self._crypto_id_map = crypto_id_map
        self._vs = vs_currency.lower()
        self._timeout = timeout

    def fetch_rates(self) -> tuple[dict[str, float], dict[str, Any]]:
        ids = ",".join(self._crypto_id_map.values())
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {"ids": ids, "vs_currencies": self._vs}

        started = perf_counter()
        try:
            resp = requests.get(url, params=params, timeout=self._timeout)
        except requests.exceptions.RequestException as e:
            raise ApiRequestError(f"CoinGecko: ошибка сети: {e}") from e
        ms = int((perf_counter() - started) * 1000)

        if resp.status_code != 200:
            raise ApiRequestError(f"CoinGecko: HTTP {resp.status_code}")

        try:
            payload = resp.json()
        except ValueError as e:
            raise ApiRequestError("CoinGecko: некорректный JSON") from e

        out: dict[str, float] = {}
        inv_map = {v: k for k, v in self._crypto_id_map.items()} 

        for raw_id, obj in payload.items():
            ticker = inv_map.get(raw_id)
            if not ticker:
                continue
            val = obj.get(self._vs)
            if isinstance(val, (int, float)):
                out[f"{ticker}_USD"] = float(val)

        meta = {
            "source": "CoinGecko",
            "status_code": resp.status_code,
            "request_ms": ms,
            "etag": resp.headers.get("ETag"),
        }
        return out, meta


class ExchangeRateApiClient(BaseApiClient):
    def __init__(self, api_key: str | None, base_currency: str, timeout: int = 10) -> None:
        self._api_key = api_key
        self._base = base_currency.upper()
        self._timeout = timeout

    def fetch_rates(self) -> tuple[dict[str, float], dict[str, Any]]:
        if not self._api_key:
            raise ApiRequestError("ExchangeRate-API: не задан EXCHANGERATE_API_KEY")

        url = f"https://v6.exchangerate-api.com/v6/{self._api_key}/latest/{self._base}"

        started = perf_counter()
        try:
            resp = requests.get(url, timeout=self._timeout)
        except requests.exceptions.RequestException as e:
            raise ApiRequestError(f"ExchangeRate-API: ошибка сети: {e}") from e
        ms = int((perf_counter() - started) * 1000)

        if resp.status_code != 200:
            raise ApiRequestError(f"ExchangeRate-API: HTTP {resp.status_code}")

        try:
            payload = resp.json()
        except ValueError as e:
            raise ApiRequestError("ExchangeRate-API: некорректный JSON") from e

        if payload.get("result") != "success":
            raise ApiRequestError(f"ExchangeRate-API: result={payload.get('result')}")

        rates_obj = payload.get("conversion_rates") or payload.get("rates")
        if not isinstance(rates_obj, dict):
            raise ApiRequestError("ExchangeRate-API: отсутствует rates")

        out: dict[str, float] = {}
        for k, v in rates_obj.items():
            if isinstance(k, str) and isinstance(v, (int, float)):
                out[f"{k.upper()}_{self._base}"] = float(v)

        meta = {
            "source": "ExchangeRate-API",
            "status_code": resp.status_code,
            "request_ms": ms,
        }
        return out, meta