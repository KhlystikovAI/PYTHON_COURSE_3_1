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

from valutatrade_hub.core.utils import RATES_PATH


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


def get_rate(frm: str, to: str) -> dict[str, Any]:
    """
    Возвращает rate + timestamps.
    Сначала пробуем rates.json из кэша; если отсутствует, то используем заглушку и обновляем кэш.
    """
    ensure_data_files()

    frm_c = _normalize_currency(frm)
    to_c = _normalize_currency(to)

    if frm_c == to_c:
        return {
            "from": frm_c,
            "to": to_c,
            "rate": 1.0,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "source": "Локальное хранилище",
        }

    key = f"{frm_c}_{to_c}"
    now = datetime.now()

    rates = load_json(RATES_PATH, default={})
    if not isinstance(rates, dict):
        rates = {}

    # обновление кэша: 5 минут
    fresh_seconds = 5 * 60

    if key in rates and isinstance(rates[key], dict):
        updated_at_raw = rates[key].get("updated_at")
        rate_val = rates[key].get("rate")
        if isinstance(updated_at_raw, str) and isinstance(rate_val, (int, float)):
            try:
                updated_at = datetime.fromisoformat(updated_at_raw)
                if (now - updated_at).total_seconds() <= fresh_seconds:
                    return {
                        "from": frm_c,
                        "to": to_c,
                        "rate": float(rate_val),
                        "updated_at": updated_at_raw,
                        "source": rates.get("source", "LocalCache"),
                    }
            except ValueError:
                pass  

    # возврат к базовым ставкам (на основе доллара США)
    ex = _default_exchange_rates_usd()

    def to_usd(code: str) -> float:
        pair = f"{code}_USD"
        if pair not in ex:
            raise PortfolioError(f"Не удалось получить курс для {code}→USD")
        return ex[pair]

    # вычисляем frm для использования в расчетах USD как основной валюты:
    frm_to_usd = to_usd(frm_c)
    to_to_usd = to_usd(to_c)
    rate = frm_to_usd / to_to_usd  

    updated_at_str = now.isoformat(timespec="seconds")
    rates[key] = {"rate": rate, "updated_at": updated_at_str}
    rates["source"] = "Локальное хранилище"
    rates["last_refresh"] = updated_at_str
    save_json(RATES_PATH, rates)

    return {"from": frm_c, "to": to_c, "rate": rate, "updated_at": updated_at_str, "source": "StubRates"}


def buy(user_id: int, currency: str, amount: float, base: str = "USD") -> dict[str, Any]:
    
    ensure_data_files()

    uid = int(user_id)
    cur = _normalize_currency(currency)
    base_c = _normalize_currency(base)
    amt = _parse_amount(amount)

    row = _get_portfolio_row(uid)
    wallets: dict[str, Any] = row["wallets"]

    before = float(wallets.get(cur, {}).get("balance", 0.0))
    after = before + amt
    wallets[cur] = {"balance": after}

    valuation = None
    try:
        r = get_rate(cur, base_c)
        valuation = amt * float(r["rate"])
    except PortfolioError:
        r = None

    _save_portfolio_row(row)

    result: dict[str, Any] = {
        "currency": cur,
        "amount": amt,
        "before": before,
        "after": after,
    }
    if r:
        result["rate"] = r["rate"]
        result["base"] = base_c
        result["estimated_value"] = valuation
        result["rate_updated_at"] = r["updated_at"]
    return result


def sell(user_id: int, currency: str, amount: float, base: str = "USD") -> dict[str, Any]:
    ensure_data_files()

    uid = int(user_id)
    cur = _normalize_currency(currency)
    base_c = _normalize_currency(base)
    amt = _parse_amount(amount)

    row = _get_portfolio_row(uid)
    wallets: dict[str, Any] = row["wallets"]

    if cur not in wallets:
        raise PortfolioError(
            f"У вас нет кошелька '{cur}'. Добавьте валюту: она создаётся автоматически при первой покупке."
        )

    before = float(wallets[cur].get("balance", 0.0))
    if amt > before:
        raise PortfolioError(f"Недостаточно средств: доступно {before:.4f} {cur}, необходимо {amt:.4f} {cur}")

    after = before - amt
    wallets[cur] = {"balance": after}

    proceeds = None
    r = None
    try:
        r = get_rate(cur, base_c)
        proceeds = amt * float(r["rate"])
    except PortfolioError:
        pass

    _save_portfolio_row(row)

    result: dict[str, Any] = {
        "currency": cur,
        "amount": amt,
        "before": before,
        "after": after,
    }
    if r:
        result["rate"] = r["rate"]
        result["base"] = base_c
        result["estimated_proceeds"] = proceeds
        result["rate_updated_at"] = r["updated_at"]
    return result


def show_portfolio(user_id: int, base: str = "USD") -> dict[str, Any]:
    ensure_data_files()

    uid = int(user_id)
    base_c = _normalize_currency(base)

    row = _get_portfolio_row(uid)
    wallets: dict[str, Any] = row.get("wallets", {})

    items: list[dict[str, Any]] = []
    total = 0.0

    # проверяем известна ли базовая валюта (с помощью get_rate)
    try:
        _ = get_rate("USD", base_c)
    except PortfolioError:
        raise PortfolioError(f"Неизвестная базовая валюта '{base_c}'")

    for code, payload in wallets.items():
        cur = _normalize_currency(code)
        bal = float(payload.get("balance", 0.0))

        if bal == 0.0:
            pass

        if cur == base_c:
            value = bal
            rate = 1.0
        else:
            r = get_rate(cur, base_c)
            rate = float(r["rate"])
            value = bal * rate

        total += value
        items.append(
            {
                "currency": cur,
                "balance": bal,
                "rate_to_base": rate,
                "value_in_base": value,
            }
        )

    return {"user_id": uid, "base": base_c, "items": items, "total": total}