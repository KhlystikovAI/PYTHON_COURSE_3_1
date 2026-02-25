from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.parser_service.api_clients import BaseApiClient
from valutatrade_hub.parser_service.storage import RatesStorage

logger = logging.getLogger("valutatrade")


def _utc_iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class RatesUpdater:
    def __init__(self, storage: RatesStorage, clients: list[BaseApiClient]) -> None:
        self._storage = storage
        self._clients = clients

    def run_update(self) -> dict[str, Any]:
        started = datetime.now(timezone.utc)
        ts = _utc_iso_z(started)

        logger.info("PARSER ОБНОВЛЯЕТ КУРСЫ...")

        merged: dict[str, dict[str, Any]] = {} 
        history_records: list[dict[str, Any]] = []
        errors: list[str] = []

        for client in self._clients:
            try:
                rates, meta = client.fetch_rates()
                source = str(meta.get("source", "Unknown"))
                logger.info("PARSER ЗАГРУЖАЕТ %s... OK (%s rates)", source, len(rates))

                for pair, rate in rates.items():
                    if not isinstance(rate, (int, float)):
                        continue

                    if "_" not in pair:
                        continue
                    frm, to = pair.split("_", 1)
                    frm = frm.upper()
                    to = to.upper()

                    rec_id = f"{frm}_{to}_{ts}"

                    history_records.append(
                        {
                            "id": rec_id,
                            "from_currency": frm,
                            "to_currency": to,
                            "rate": float(rate),
                            "timestamp": ts,
                            "source": source,
                            "meta": meta,
                        }
                    )

                    merged[pair] = {"rate": float(rate), "updated_at": ts, "source": source}

            except ApiRequestError as e:
                msg = str(e)
                errors.append(msg)
                logger.error("PARSER НЕ СМОГ ОБНОВИТЬ: %s", msg)
            except Exception as e:
                msg = f"Неожиданная ошибка клиента: {type(e).__name__}: {e}"
                errors.append(msg)
                logger.error("PARSER %s", msg)

        if history_records:
            self._storage.append_history_records(history_records)

        snapshot = self._storage.read_rates_snapshot()
        pairs = snapshot.get("pairs")
        if not isinstance(pairs, dict):
            pairs = {}

        for pair, obj in merged.items():
            current = pairs.get(pair)
            if isinstance(current, dict) and isinstance(current.get("updated_at"), str):
                if current["updated_at"] >= obj["updated_at"]:
                    continue
            pairs[pair] = obj

        snapshot["pairs"] = pairs
        snapshot["last_refresh"] = ts
        self._storage.write_rates_snapshot(snapshot)

        logger.info("PARSER записывает %s курсы в rates.json... ГОТОВО", len(merged))

        return {
            "updated": len(merged),
            "last_refresh": ts,
            "errors": errors,
        }