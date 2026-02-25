from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ParserConfig:
    # API key из окружения
    EXCHANGERATE_API_KEY: str | None = os.getenv("EXCHANGERATE_API_KEY")

    COINGECKO_URL: str = "https://api.coingecko.com/api/v3/simple/price"
    EXCHANGERATE_API_URL: str = "https://v6.exchangerate-api.com/v6"

    BASE_CURRENCY: str = "USD"
    FIAT_CURRENCIES: tuple[str, ...] = ("EUR", "GBP", "RUB")
    CRYPTO_CURRENCIES: tuple[str, ...] = ("BTC", "ETH", "SOL")
    CRYPTO_ID_MAP: dict[str, str] = None  # set in __post_init__

    RATES_FILE_PATH: str = "data/rates.json"
    HISTORY_FILE_PATH: str = "data/exchange_rates.json"

    REQUEST_TIMEOUT: int = 10

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "CRYPTO_ID_MAP",
            {"BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana"},
        )

    @property
    def rates_path(self) -> Path:
        return Path(self.RATES_FILE_PATH)

    @property
    def history_path(self) -> Path:
        return Path(self.HISTORY_FILE_PATH)