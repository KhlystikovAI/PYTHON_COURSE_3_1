from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from valutatrade_hub.infra.settings import SettingsLoader


def setup_logging() -> None:
    settings = SettingsLoader()
    logs_dir = settings.get("logs_dir")
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = settings.get("actions_log")

    logger = logging.getLogger("valutatrade")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    handler = RotatingFileHandler(
        log_path,
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    formatter = logging.Formatter("%(levelname)s %(asctime)s %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)