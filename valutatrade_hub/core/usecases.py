from __future__ import annotations

from datetime import datetime
import secrets
from typing import Any

from valutatrade_hub.core.models import User, ValidationError
from valutatrade_hub.core.utils import (
    PORTFOLIOS_PATH,
    USERS_PATH,
    ensure_data_files,
    load_json,
    save_json,
)


from valutatrade_hub.core.currencies import get_currency
from valutatrade_hub.core.exceptions import ApiRequestError, CurrencyNotFoundError
from valutatrade_hub.decorators import log_action
from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.infra.settings import SettingsLoader
from valutatrade_hub.core.models import Wallet


class AuthError(RuntimeError):
    """Ошибка login/register."""


def _next_user_id(users: list[dict[str, Any]]) -> int:
    if not users:
        return 1
    return max(int(u.get("user_id", 0)) for u in users) + 1


def register(username: str, password: str) -> str:
    ensure_data_files()

    if not isinstance(username, str) or not username.strip():
        raise AuthError("Имя пользователя не может быть пустым")
    if not isinstance(password, str) or len(password) < 4:
        raise AuthError("Пароль должен быть не короче 4 символов")

    users = load_json(USERS_PATH, default=[])
    if not isinstance(users, list):
        raise AuthError("users.json поврежден")

    username_norm = username.strip()

    if any(u.get("username") == username_norm for u in users):
        raise AuthError(f"Имя пользователя '{username_norm}' уже занято")

    user_id = _next_user_id(users)
    salt = secrets.token_hex(8)
    registration_date = datetime.now()

# Временно
    user = User(
        user_id=user_id,
        username=username_norm,
        hashed_password="",
        salt=salt,
        registration_date=registration_date,
    )
    user.change_password(password)

    users.append(
        {
            "user_id": user.user_id,
            "username": user.username,
            "hashed_password": user.hashed_password,
            "salt": user.salt,
            "registration_date": user.registration_date.isoformat(),
        }
    )
    save_json(USERS_PATH, users)

    portfolios = load_json(PORTFOLIOS_PATH, default=[])
    if not isinstance(portfolios, list):
        raise AuthError("portfolios.json поврежден")

    portfolios.append({"user_id": user.user_id, "wallets": {}})
    save_json(PORTFOLIOS_PATH, portfolios)

    return (
        f"Пользователь '{user.username}' зарегистрирован (id={user.user_id}). "
        f"Войдите: login --username {user.username} --password ****"
    )


def login(username: str, password: str) -> User:
    ensure_data_files()

    if not isinstance(username, str) or not username.strip():
        raise AuthError("Username обязателен")
    if not isinstance(password, str) or not password:
        raise AuthError("Password обязателен")

    users = load_json(USERS_PATH, default=[])
    if not isinstance(users, list):
        raise AuthError("users.json поврежден")

    username_norm = username.strip()

    row = next((u for u in users if u.get("username") == username_norm), None)
    if row is None:
        raise AuthError(f"Пользователь '{username_norm}' не найден")

    try:
        user = User(
            user_id=int(row["user_id"]),
            username=str(row["username"]),
            hashed_password=str(row["hashed_password"]),
            salt=str(row["salt"]),
            registration_date=datetime.fromisoformat(str(row["registration_date"])),
        )
    except (KeyError, ValueError, ValidationError) as e:
        raise AuthError("Некорректные данные пользователя в users.json") from e

    if not user.verify_password(password):
        raise AuthError("Неверный пароль")

    return user


class PortfolioError(RuntimeError):
    """Ошибка portfolio/trading."""


def _normalize_currency(code: str) -> str:
    if not isinstance(code, str):
        raise PortfolioError("Код валюты должен быть строкой")
    code = code.strip().upper()
    if not code:
        raise PortfolioError("Код валюты не может быть пустым")
    return code


def _parse_amount(amount: float) -> float:
    if not isinstance(amount, (int, float)):
        raise PortfolioError(" Сумма должна быть положительным числом")
    x = float(amount)
    if x <= 0:
        raise PortfolioError(" Сумма должна быть положительным числом")
    return x


def _load_portfolios() -> list[dict[str, Any]]:
    portfolios = load_json(PORTFOLIOS_PATH, default=[])
    if not isinstance(portfolios, list):
        raise PortfolioError("portfolios.json поврежден")
    return portfolios


def _get_portfolio_row(user_id: int) -> dict[str, Any]:
    portfolios = _load_portfolios()
    row = next((p for p in portfolios if int(p.get("user_id", -1)) == int(user_id)), None)
    if row is None:
        # если нет записи — создаём пустую
        row = {"user_id": int(user_id), "wallets": {}}
        portfolios.append(row)
        save_json(PORTFOLIOS_PATH, portfolios)
    if "wallets" not in row or not isinstance(row["wallets"], dict):
        row["wallets"] = {}
    return row


def _save_portfolio_row(updated_row: dict[str, Any]) -> None:
    portfolios = _load_portfolios()
    uid = int(updated_row["user_id"])
    for i, p in enumerate(portfolios):
        if int(p.get("user_id", -1)) == uid:
            portfolios[i] = updated_row
            save_json(PORTFOLIOS_PATH, portfolios)
            return
    portfolios.append(updated_row)
    save_json(PORTFOLIOS_PATH, portfolios)


def _default_exchange_rates_usd() -> dict[str, float]:
    # 1 UNIT = X USD
    return {
        "USD_USD": 1.0,
        "EUR_USD": 1.0786,
        "BTC_USD": 59337.21,
        "RUB_USD": 0.01016,
        "ETH_USD": 3720.00,
    }


def get_rate(from_code: str, to_code: str) -> dict[str, Any]:
    settings = SettingsLoader()
    ttl: int = int(settings.get("rates_ttl_seconds", 300))

    # валидация через реестр
    frm = _normalize_currency_code(from_code)  # CurrencyNotFoundError если неизвестно
    to = _normalize_currency_code(to_code)

    if frm == to:
        return {
            "from": frm,
            "to": to,
            "rate": 1.0,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }

    db = DatabaseManager()
    rates = db.read_rates()
    if not isinstance(rates, dict):
        rates = {}

    key = f"{frm}_{to}"
    now = datetime.now()

    cached = rates.get(key)
    if isinstance(cached, dict):
        rate_val = cached.get("rate")
        updated_at_raw = cached.get("updated_at")
        if isinstance(rate_val, (int, float)) and isinstance(updated_at_raw, str):
            try:
                updated_at = datetime.fromisoformat(updated_at_raw)
                age = (now - updated_at).total_seconds()
                if age <= ttl:
                    return {"from": frm, "to": to, "rate": float(rate_val), "updated_at": updated_at_raw}
            except ValueError:
                pass

    # кеша нет — пробуем обновить
    try:
        ex = _stub_rates_usd()

        def to_usd(code: str) -> float:
            pair = f"{code}_USD"
            if pair not in ex:
                raise CurrencyNotFoundError(code)
            return ex[pair]

        frm_to_usd = to_usd(frm)
        to_to_usd = to_usd(to)
        rate = frm_to_usd / to_to_usd

        updated_at_str = now.isoformat(timespec="seconds")
        rates[key] = {"rate": rate, "updated_at": updated_at_str}
        rates["source"] = "Локальный источник (заглушка)"
        rates["last_refresh"] = updated_at_str
        db.write_rates(rates)

        return {"from": frm, "to": to, "rate": rate, "updated_at": updated_at_str}
    except CurrencyNotFoundError:
        raise
    except Exception as e:
        # по ТЗ — ApiRequestError
        raise ApiRequestError(str(e)) from e

@log_action("BUY", verbose=True)
def buy(user_id: int, currency_code: str, amount: float, base: str = "USD") -> dict[str, Any]:
    db = DatabaseManager()
    uid = int(user_id)

    user_row = _find_user_row(db, uid)
    username = str(user_row.get("username", ""))

    cur = _normalize_currency_code(currency_code)  # CurrencyNotFoundError
    base_c = _normalize_currency_code(base)
    amt = _parse_amount(amount)

    row = _load_portfolio_row(db, uid)
    wallets: dict[str, Any] = row["wallets"]

    before = float(wallets.get(cur, {}).get("balance", 0.0))
    wallet = Wallet(cur, before)
    wallet.deposit(amt)
    after = wallet.balance

    wallets[cur] = {"balance": after}
    _save_portfolio_row(db, row)

    # оценка стоимости
    rate_info = get_rate(cur, base_c)  # CurrencyNotFoundError/ApiRequestError
    estimated_value = amt * float(rate_info["rate"])

    return {
        "user_id": uid,
        "username": username,
        "currency": cur,
        "amount": amt,
        "before": before,
        "after": after,
        "base": base_c,
        "rate": rate_info["rate"],
        "rate_updated_at": rate_info["updated_at"],
        "estimated_value": estimated_value,
    }


@log_action("SELL", verbose=True)
def sell(user_id: int, currency_code: str, amount: float, base: str = "USD") -> dict[str, Any]:
    db = DatabaseManager()
    uid = int(user_id)

    user_row = _find_user_row(db, uid)
    username = str(user_row.get("username", ""))

    cur = _normalize_currency_code(currency_code)  # CurrencyNotFoundError
    base_c = _normalize_currency_code(base)
    amt = _parse_amount(amount)

    row = _load_portfolio_row(db, uid)
    wallets: dict[str, Any] = row["wallets"]

    if cur not in wallets:

        raise ValueError(
            f"У вас нет кошелька '{cur}'. Валюта создаётся автоматически при первой покупке."
        )

    before = float(wallets[cur].get("balance", 0.0))
    wallet = Wallet(cur, before)

    wallet.withdraw(amt)
    after = wallet.balance

    wallets[cur] = {"balance": after}
    _save_portfolio_row(db, row)

    rate_info = get_rate(cur, base_c)  # CurrencyNotFoundError/ApiRequestError
    estimated_proceeds = amt * float(rate_info["rate"])

    return {
        "user_id": uid,
        "username": username,
        "currency": cur,
        "amount": amt,
        "before": before,
        "after": after,
        "base": base_c,
        "rate": rate_info["rate"],
        "rate_updated_at": rate_info["updated_at"],
        "estimated_proceeds": estimated_proceeds,
    }


def show_portfolio(user_id: int, base: str = "USD") -> dict[str, Any]:
    db = DatabaseManager()
    uid = int(user_id)

    # валидируем через реестр
    base_c = _normalize_currency_code(base)

    row = _load_portfolio_row(db, uid)
    wallets: dict[str, Any] = row.get("wallets", {})

    items: list[dict[str, Any]] = []
    total = 0.0

    for code, payload in wallets.items():
        # валидируем код через реестр
        cur = _normalize_currency_code(code)

        bal_raw = payload.get("balance", 0.0)
        if not isinstance(bal_raw, (int, float)):
            raise ApiRequestError(f"Некорректный баланс в portfolios.json для {cur}")

        bal = float(bal_raw)

        if cur == base_c:
            rate = 1.0
            value = bal
            updated_at = None
        else:
            rate_info = get_rate(cur, base_c) 
            rate = float(rate_info["rate"])
            updated_at = rate_info.get("updated_at")
            value = bal * rate

        total += value
        items.append(
            {
                "currency": cur,
                "balance": bal,
                "rate_to_base": rate,
                "value_in_base": value,
                "rate_updated_at": updated_at,
            }
        )

    return {"user_id": uid, "base": base_c, "items": items, "total": total}


def _normalize_currency_code(code: str) -> str:
    # Валидация через реестр
    cur = get_currency(code)
    return cur.code


def _parse_amount(amount: float) -> float:
    if not isinstance(amount, (int, float)):
        raise ValueError(" Количество должно быть положительным числом")
    value = float(amount)
    if value <= 0:
        raise ValueError(" Количество должно быть положительным числом")
    return value


def _find_user_row(db: DatabaseManager, user_id: int) -> dict[str, Any]:
    users = db.read_users()
    if not isinstance(users, list):
        raise ApiRequestError("users.json поврежден")
    row = next((u for u in users if int(u.get("user_id", -1)) == int(user_id)), None)
    if row is None:
        raise ApiRequestError(f"Пользователь id={user_id} не найден")
    return row


def _load_portfolio_row(db: DatabaseManager, user_id: int) -> dict[str, Any]:
    portfolios = db.read_portfolios()
    if not isinstance(portfolios, list):
        raise ApiRequestError("portfolios.json поврежден")

    row = next((p for p in portfolios if int(p.get("user_id", -1)) == int(user_id)), None)
    if row is None:
        row = {"user_id": int(user_id), "wallets": {}}
        portfolios.append(row)
        db.write_portfolios(portfolios)

    if "wallets" not in row or not isinstance(row["wallets"], dict):
        row["wallets"] = {}

    return row


def _save_portfolio_row(db: DatabaseManager, updated_row: dict[str, Any]) -> None:
    portfolios = db.read_portfolios()
    if not isinstance(portfolios, list):
        raise ApiRequestError("portfolios.json поврежден")

    uid = int(updated_row["user_id"])
    for i, p in enumerate(portfolios):
        if int(p.get("user_id", -1)) == uid:
            portfolios[i] = updated_row
            db.write_portfolios(portfolios)
            return

    portfolios.append(updated_row)
    db.write_portfolios(portfolios)


def _stub_rates_usd() -> dict[str, float]:
    return {
        "USD_USD": 1.0,
        "EUR_USD": 1.0786,
        "BTC_USD": 59337.21,
        "RUB_USD": 0.01016,
        "ETH_USD": 3720.00,
    }