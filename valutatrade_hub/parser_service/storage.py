from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


class RatesStorage:
    def __init__(self, rates_path: Path, history_path: Path) -> None:
        self._rates_path = rates_path
        self._history_path = history_path

    def read_rates_snapshot(self) -> dict[str, Any]:
        if not self._rates_path.exists():
            return {"pairs": {}, "last_refresh": None}
        raw = self._rates_path.read_text(encoding="utf-8").strip()
        if not raw:
            return {"pairs": {}, "last_refresh": None}
        return json.loads(raw)

    def write_rates_snapshot(self, snapshot: dict[str, Any]) -> None:
        _atomic_write_json(self._rates_path, snapshot)

    def read_history(self) -> list[dict[str, Any]]:
        if not self._history_path.exists():
            return []
        raw = self._history_path.read_text(encoding="utf-8").strip()
        if not raw:
            return []
        return json.loads(raw)

    def append_history_records(self, records: list[dict[str, Any]]) -> None:
        history = self.read_history()
        # защита от дублей по id
        existing = {r.get("id") for r in history if isinstance(r, dict)}
        for r in records:
            if r.get("id") not in existing:
                history.append(r)
        _atomic_write_json(self._history_path, history)