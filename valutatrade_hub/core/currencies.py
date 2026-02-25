from __future__ import annotations

from abc import ABC, abstractmethod

from valutatrade_hub.core.exceptions import CurrencyNotFoundError


class Currency(ABC):
    def __init__(self, name: str, code: str) -> None:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("name не может быть пустым")
        if not isinstance(code, str):
            raise ValueError("code должен быть строкой")

        code_norm = code.strip().upper()
        if not (2 <= len(code_norm) <= 5) or " " in code_norm or not code_norm.isalnum():
            raise ValueError("code должен быть в верхнем регистре, 2–5 символов, без пробелов")

        self.name: str = name.strip()
        self.code: str = code_norm

    @abstractmethod
    def get_display_info(self) -> str:
        raise NotImplementedError


class FiatCurrency(Currency):
    def __init__(self, name: str, code: str, issuing_country: str) -> None:
        super().__init__(name=name, code=code)
        if not isinstance(issuing_country, str) or not issuing_country.strip():
            raise ValueError("issuing_country не может быть пустым")
        self.issuing_country: str = issuing_country.strip()

    def get_display_info(self) -> str:
        return f"[FIAT] {self.code} — {self.name} (Issuing: {self.issuing_country})"


class CryptoCurrency(Currency):
    def __init__(self, name: str, code: str, algorithm: str, market_cap: float) -> None:
        super().__init__(name=name, code=code)
        if not isinstance(algorithm, str) or not algorithm.strip():
            raise ValueError("algorithm не может быть пустым")
        if not isinstance(market_cap, (int, float)) or float(market_cap) < 0:
            raise ValueError("market_cap должен быть числом >= 0")

        self.algorithm: str = algorithm.strip()
        self.market_cap: float = float(market_cap)

    def get_display_info(self) -> str:
        return f"[CRYPTO] {self.code} — {self.name} (Algo: {self.algorithm}, MCAP: {self.market_cap:.2e})"


# Реестр валют (минимально нужный набор под ваши usecases)
_REGISTRY: dict[str, Currency] = {
    "USD": FiatCurrency("US Dollar", "USD", "United States"),
    "EUR": FiatCurrency("Euro", "EUR", "Eurozone"),
    "RUB": FiatCurrency("Russian Ruble", "RUB", "Russia"),
    "BTC": CryptoCurrency("Bitcoin", "BTC", "SHA-256", 1.12e12),
    "ETH": CryptoCurrency("Ethereum", "ETH", "Ethash", 4.50e11),
}


def get_currency(code: str) -> Currency:
    if not isinstance(code, str):
        raise CurrencyNotFoundError(str(code))
    key = code.strip().upper()
    cur = _REGISTRY.get(key)
    if cur is None:
        raise CurrencyNotFoundError(key)
    return cur