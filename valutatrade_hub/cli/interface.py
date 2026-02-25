from __future__ import annotations

import shlex
from typing import Any

from prettytable import PrettyTable

from valutatrade_hub.core.usecases import (
    AuthError,
    buy,
    get_rate,
    login,
    register,
    sell,
    show_portfolio,
)
from valutatrade_hub.core.exceptions import ApiRequestError, CurrencyNotFoundError, InsufficientFundsError

from valutatrade_hub.logging_config import setup_logging
from valutatrade_hub.parser_service.api_clients import CoinGeckoClient, ExchangeRateApiClient
from valutatrade_hub.parser_service.config import ParserConfig
from valutatrade_hub.parser_service.storage import RatesStorage
from valutatrade_hub.parser_service.updater import RatesUpdater

class CLIError(Exception):
    pass


def _parse_kv_args(tokens: list[str]) -> dict[str, str]:
    """
    Парсер для 2х значений
    """
    args: dict[str, str] = {}
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if not t.startswith("--"):
            raise CLIError(f"Неожиданный аргумент: {t}")
        key = t[2:]
        if not key:
            raise CLIError("Некорректный аргумент")
        if i + 1 >= len(tokens):
            raise CLIError(f"Для аргумента --{key} не задано значение")
        val = tokens[i + 1]
        args[key] = val
        i += 2
    return args


def _require_login(current_user: dict[str, Any] | None) -> dict[str, Any]:
    if not current_user:
        raise CLIError("Сначала выполните login")
    return current_user


def _cmd_register(argv: list[str]) -> str:
    kv = _parse_kv_args(argv)
    username = kv.get("username")
    password = kv.get("password")
    if not username:
        raise CLIError("--username обязателен")
    if password is None:
        raise CLIError("--password обязателен")
    return register(username=username, password=password)


def _cmd_login(argv: list[str]) -> dict[str, Any]:
    kv = _parse_kv_args(argv)
    username = kv.get("username")
    password = kv.get("password")
    if not username:
        raise CLIError("--username обязателен")
    if password is None:
        raise CLIError("--password обязателен")
    user = login(username=username, password=password)
    return {"user_id": user.user_id, "username": user.username}


def _cmd_get_rate(argv: list[str]) -> str:
    kv = _parse_kv_args(argv)
    frm = kv.get("from")
    to = kv.get("to")
    if not frm:
        raise CLIError("--from обязателен")
    if not to:
        raise CLIError("--to обязателен")

    r = get_rate(frm, to)
    inv = get_rate(to, frm)

    return (
        f"Курс {r['from']}→{r['to']}: {r['rate']:.8f} (обновлено: {r['updated_at']})\n"
        f"Обратный курс {inv['from']}→{inv['to']}: {inv['rate']:.8f}"
    )


def _cmd_show_portfolio(argv: list[str], current_user: dict[str, Any] | None) -> str:
    user = _require_login(current_user)
    kv = _parse_kv_args(argv) if argv else {}
    base = kv.get("base", "USD")

    data = show_portfolio(user_id=user["user_id"], base=base)

    table = PrettyTable()
    table.field_names = ["Валюта", "Баланс", f"В {data['base']}"]

    if not data["items"]:
        return f"Портфель пользователя '{user['username']}' пуст."

    for item in data["items"]:
        table.add_row(
            [
                item["currency"],
                f"{item['balance']:.4f}",
                f"{item['value_in_base']:.4f} {data['base']}",
            ]
        )

    out = [
        f"Портфель пользователя '{user['username']}' (база: {data['base']}):",
        str(table),
        f"ИТОГО: {data['total']:.4f} {data['base']}",
    ]
    return "\n".join(out)


def _cmd_buy(argv: list[str], current_user: dict[str, Any] | None) -> str:
    user = _require_login(current_user)
    kv = _parse_kv_args(argv)
    currency = kv.get("currency")
    amount_raw = kv.get("amount")
    if not currency:
        raise CLIError("--currency обязателен")
    if amount_raw is None:
        raise CLIError("--amount обязателен")

    try:
        amount = float(amount_raw)
    except ValueError as e:
        raise CLIError(" Сумма должна быть положительным числом") from e

    result = buy(user_id=user["user_id"], currency_code=currency, amount=amount, base="USD")

    lines = [
        f"Покупка выполнена: {result['amount']:.4f} {result['currency']}"
        + (
            f" по курсу {result['rate']:.2f} {result['base']}/{result['currency']}"
            if "rate" in result
            else ""
        ),
        "Изменения в портфеле:",
        f"- {result['currency']}: было {result['before']:.4f} → стало {result['after']:.4f}",
    ]
    if "estimated_value" in result and result["estimated_value"] is not None:
        lines.append(f"Оценочная стоимость покупки: {result['estimated_value']:.2f} USD")
    return "\n".join(lines)


def _cmd_sell(argv: list[str], current_user: dict[str, Any] | None) -> str:
    user = _require_login(current_user)
    kv = _parse_kv_args(argv)
    currency = kv.get("currency")
    amount_raw = kv.get("amount")
    if not currency:
        raise CLIError("--Укажите валюту")
    if amount_raw is None:
        raise CLIError("--Укажите сумму")

    try:
        amount = float(amount_raw)
    except ValueError as e:
        raise CLIError(" Сумма должна быть положительным числом") from e

    result = sell(user_id=user["user_id"], currency_code=currency, amount=amount, base="USD")

    lines = [
        f"Продажа выполнена: {result['amount']:.4f} {result['currency']}"
        + (
            f" по курсу {result['rate']:.2f} {result['base']}/{result['currency']}"
            if "rate" in result
            else ""
        ),
        "Изменения в портфеле:",
        f"- {result['currency']}: было {result['before']:.4f} → стало {result['after']:.4f}",
    ]
    if "estimated_proceeds" in result and result["estimated_proceeds"] is not None:
        lines.append(f"Оценочная выручка: {result['estimated_proceeds']:.2f} USD")
    return "\n".join(lines)


def _help() -> str:
    return (
        "Доступные команды:\n"
        "  register --username <str> --password <str>\n"
        "  login --username <str> --password <str>\n"
        "  show-portfolio [--base <str>]\n"
        "  buy --currency <str> --amount <float>\n"
        "  sell --currency <str> --amount <float>\n"
        "  get-rate --from <str> --to <str>\n"
        "  help\n"
        "  exit\n"
        "  update-rates [--source coingecko|exchangerate]"
        "  show-rates [--currency <str>] [--top <int>] [--base <str>]"
    )
def _cmd_update_rates(argv: list[str]) -> str:
    kv = _parse_kv_args(argv) if argv else {}
    source = (kv.get("source") or "").strip().lower()  # coingecko / exchangerate / empty

    cfg = ParserConfig()
    storage = RatesStorage(cfg.rates_path, cfg.history_path)

    clients = []
    if source in {"", "coingecko"}:
        clients.append(CoinGeckoClient(cfg.CRYPTO_ID_MAP, vs_currency=cfg.BASE_CURRENCY, timeout=cfg.REQUEST_TIMEOUT))
    if source in {"", "exchangerate"}:
        clients.append(ExchangeRateApiClient(cfg.EXCHANGERATE_API_KEY, base_currency=cfg.BASE_CURRENCY, timeout=cfg.REQUEST_TIMEOUT))

    updater = RatesUpdater(storage=storage, clients=clients)
    result = updater.run_update()

    if result["errors"]:
        return (
            "Update завршен с ошибками.\n"
            f"Обновлено курсов: {result['updated']}. Последнее обновление: {result['last_refresh']}\n"
            "Проверьте logs/actions.log для деталей."
        )

    return f"Обновление успешно. Всего курсов обновлено: {result['updated']}. Последнее обновление: {result['last_refresh']}"

def _cmd_show_rates(argv: list[str]) -> str:
    kv = _parse_kv_args(argv) if argv else {}
    currency = (kv.get("currency") or "").strip().upper()
    base = (kv.get("base") or "USD").strip().upper()
    top_raw = kv.get("top")

    cfg = ParserConfig()
    storage = RatesStorage(cfg.rates_path, cfg.history_path)
    snap = storage.read_rates_snapshot()

    pairs = snap.get("pairs")
    if not isinstance(pairs, dict) or not pairs:
        return "Локальный кэш пуст. Выполните 'update-rates', чтобы загрузить данные."

    last_refresh = snap.get("last_refresh")

    # фильтруем пары по base (TO)
    rows = []
    for pair, obj in pairs.items():
        if not isinstance(obj, dict):
            continue
        if "_" not in pair:
            continue
        frm, to = pair.split("_", 1)
        if to.upper() != base:
            continue
        rate = obj.get("rate")
        updated_at = obj.get("updated_at")
        if not isinstance(rate, (int, float)):
            continue
        if currency and frm.upper() != currency:
            continue
        rows.append((pair.upper(), float(rate), str(updated_at) if updated_at else ""))

    if currency and not rows:
        return f"Курс для '{currency}' не найден в кэше."

    # сортировка
    if top_raw is not None:
        try:
            top_n = int(top_raw)
        except ValueError as e:
            raise CLIError("--top должен быть числом") from e
        rows.sort(key=lambda x: x[1], reverse=True)
        rows = rows[: max(top_n, 0)]
    else:
        rows.sort(key=lambda x: x[0])

    table = PrettyTable()
    table.field_names = ["Пара", "Курс", "Обновлено"]
    for pair, rate, upd in rows:
        table.add_row([pair, rate, upd])

    header = f"Курсы из кэша (обновлены {last_refresh}):"
    return header + "\n" + str(table)


def main() -> None:
    setup_logging()
    print("ValutaTrade Hub. Type 'help' for commands.")
    current_user: dict[str, Any] | None = None

    while True:
        try:
            raw = input("> ").strip()
            if not raw:
                continue

            parts = shlex.split(raw)
            cmd, argv = parts[0], parts[1:]

            if cmd in {"exit", "quit"}:
                print("Выход.")
                return

            if cmd == "help":
                print(_help())
                continue

            if cmd == "register":
                print(_cmd_register(argv))
                continue

            if cmd == "login":
                current_user = _cmd_login(argv)
                print(f"Вы вошли как '{current_user['username']}'")
                continue

            if cmd == "show-portfolio":
                print(_cmd_show_portfolio(argv, current_user))
                continue

            if cmd == "buy":
                print(_cmd_buy(argv, current_user))
                continue

            if cmd == "sell":
                print(_cmd_sell(argv, current_user))
                continue

            if cmd == "get-rate":
                print(_cmd_get_rate(argv))
                continue

            if cmd == "update-rates":
                print(_cmd_update_rates(argv))
                continue

            if cmd == "show-rates":
                print(_cmd_show_rates(argv))
                continue

            print(f"Неизвестная команда: {cmd}. Введите 'help'.")

        except InsufficientFundsError as e:
            # печатаем как есть (по заданию)
            print(str(e))

        except CurrencyNotFoundError as e:
            # подсказка help get-rate или список кодов (по заданию)
            print(str(e))
            print("Подсказка: используйте get-rate или проверьте код валюты.")
            print("Поддерживаемые коды: USD, EUR, RUB, BTC, ETH")

        except ApiRequestError as e:
            print(str(e))
            print("Подсказка: повторите позже или проверьте сеть/доступ к источнику курсов.")

        except (AuthError, CLIError, ValueError) as e:
            # ValueError используем для пользовательских ошибок типа "нет кошелька"
            print(str(e))

        except KeyboardInterrupt:
            print("\nВыход.")

        except Exception as e:
            print(f"Внутренняя ошибка: {type(e).__name__}: {e}")
            return
