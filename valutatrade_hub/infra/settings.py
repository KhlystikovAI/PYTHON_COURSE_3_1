from __future__ import annotations

from pathlib import Path
from typing import Any


class SettingsLoader:
    _instance: "SettingsLoader | None" = None

    def __new__(cls) -> "SettingsLoader":
        # Выбран __new__: простая реализация Singleton.
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_once()
        return cls._instance

    def _init_once(self) -> None:
        base_dir = Path(__file__).resolve().parents[2]  # корень проекта
        self._data_dir = base_dir / "data"
        self._rates_ttl_seconds = 300  # 5 минут по ТЗ
        self._default_base_currency = "USD"
        self._logs_dir = base_dir / "logs"
        self._actions_log = self._logs_dir / "actions.log"

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, f"_{key}", default)

    def reload(self) -> None:
        
        self._init_once()