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
    )


def main() -> None:
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
