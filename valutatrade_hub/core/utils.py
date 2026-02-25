from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


class StorageError(RuntimeError):
    pass


DATA_DIR = Path(__file__).resolve().parents[2] / "data"
USERS_PATH = DATA_DIR / "users.json"
PORTFOLIOS_PATH = DATA_DIR / "portfolios.json"
RATES_PATH = DATA_DIR / "rates.json"


def ensure_data_files() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if not USERS_PATH.exists():
        USERS_PATH.write_text("[]\n", encoding="utf-8")
    if not PORTFOLIOS_PATH.exists():
        PORTFOLIOS_PATH.write_text("[]\n", encoding="utf-8")
    if not RATES_PATH.exists():
        RATES_PATH.write_text("{}\n", encoding="utf-8")


def load_json(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            return default
        return json.loads(text)
    except (OSError, json.JSONDecodeError) as e:
        raise StorageError(f"Ошибка чтения JSON: {path}") from e


def save_json(path: Path, data: Any) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError as e:
        raise StorageError(f"Ошибка записи JSON: {path}") from e


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_currency(code: str) -> str:
    if not isinstance(code, str):
        raise ValueError("currency_code должно быть string")
    code = code.strip().upper()
    if not code:
        raise ValueError("currency_code не может быть пустым")
    return code


def parse_positive_float(value: str) -> float:
    try:
        x = float(value)
    except (TypeError, ValueError) as e:
        raise ValueError("'amount' должно быть положительным числом") from e
    if x <= 0:
        raise ValueError("'amount' должно быть положительным числом")
    return x