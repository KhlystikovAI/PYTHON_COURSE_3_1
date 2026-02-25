from __future__ import annotations

from pathlib import Path
from typing import Any

from valutatrade_hub.core.utils import load_json, save_json
from valutatrade_hub.infra.settings import SettingsLoader


class DatabaseManager:
    _instance: "DatabaseManager | None" = None

    def __new__(cls) -> "DatabaseManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_once()
        return cls._instance

    def _init_once(self) -> None:
        settings = SettingsLoader()
        data_dir: Path = settings.get("data_dir")
        self.users_path = data_dir / "users.json"
        self.portfolios_path = data_dir / "portfolios.json"
        self.rates_path = data_dir / "rates.json"

    def read_users(self) -> list[dict[str, Any]]:
        return load_json(self.users_path, default=[])

    def write_users(self, users: list[dict[str, Any]]) -> None:
        save_json(self.users_path, users)

    def read_portfolios(self) -> list[dict[str, Any]]:
        return load_json(self.portfolios_path, default=[])

    def write_portfolios(self, portfolios: list[dict[str, Any]]) -> None:
        save_json(self.portfolios_path, portfolios)

    def read_rates(self) -> dict[str, Any]:
        return load_json(self.rates_path, default={})

    def write_rates(self, rates: dict[str, Any]) -> None:
        save_json(self.rates_path, rates)