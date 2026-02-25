from __future__ import annotations

import logging
import time

from valutatrade_hub.parser_service.updater import RatesUpdater

logger = logging.getLogger("valutatrade")


def run_forever(updater: RatesUpdater, interval_seconds: int) -> None:
    while True:
        updater.run_update()
        logger.info("PARSER ОЖИДАЕТ %s секунд...", interval_seconds)
        time.sleep(interval_seconds)