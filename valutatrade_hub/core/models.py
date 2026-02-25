from __future__ import annotations

from datetime import datetime
import hashlib
from typing import Any


class ValidationError(ValueError):
    """Ошибка валидации."""


class InsufficientFundsError(ValidationError):
    """Баланс недостаточен для обмена."""


class User:
    def __init__(
        self,
        user_id: int,
        username: str,
        hashed_password: str,
        salt: str,
        registration_date: datetime,
    ) -> None:
        self._user_id = int(user_id)
        self.username = username  # валидация сеттером
        self._hashed_password = str(hashed_password)
        self._salt = str(salt)
        if not isinstance(registration_date, datetime):
            raise ValidationError("registration_date не совпадает с datetime")
        self._registration_date = registration_date

    # --- Пароль + Соль ---
    @staticmethod
    def _hash_password(password: str, salt: str) -> str:
        raw = (password + salt).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    # --- Свойства ---
    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def username(self) -> str:
        return self._username

    @username.setter
    def username(self, value: str) -> None:
        if not isinstance(value, str):
            raise ValidationError("username должно быть string")
        value = value.strip()
        if not value:
            raise ValidationError("username не может быть пустым")
        self._username = value

    @property
    def hashed_password(self) -> str:
        return self._hashed_password

    @property
    def salt(self) -> str:
        return self._salt

    @property
    def registration_date(self) -> datetime:
        return self._registration_date

    # --- methods ---
    def get_user_info(self) -> dict[str, Any]:
        """Возвращаем информацию о пользователе (без пароля)"""
        return {
            "user_id": self._user_id,
            "username": self._username,
            "registration_date": self._registration_date,
        }

    def verify_password(self, password: str) -> bool:
        if not isinstance(password, str):
            return False
        if len(password) < 4:
            # Длина пароля >= 4
            return False
        return self._hash_password(password, self._salt) == self._hashed_password

    def change_password(self, new_password: str) -> None:
        if not isinstance(new_password, str):
            raise ValidationError("пароль должен быть string")
        if len(new_password) < 4:
            raise ValidationError("пароль должен быть длиннее 4 символов")
        self._hashed_password = self._hash_password(new_password, self._salt)


class Wallet:
    def __init__(self, currency_code: str, balance: float = 0.0) -> None:
        if not isinstance(currency_code, str):
            raise ValidationError("currency_code должен быть string")
        code = currency_code.strip().upper()
        if not code:
            raise ValidationError("currency_code не иможет быть пустым")
        self.currency_code = code
        self._balance = 0.0
        self.balance = balance  # проверяется сеттером

    @property
    def balance(self) -> float:
        return self._balance

    @balance.setter
    def balance(self, value: float) -> None:
        if not isinstance(value, (int, float)):
            raise ValidationError("баланс должен быть числом")
        value_f = float(value)
        if value_f < 0:
            raise ValidationError("баланс не мождет быть отрицательным")
        self._balance = value_f

    def deposit(self, amount: float) -> None:
        if not isinstance(amount, (int, float)):
            raise ValidationError("'amount' должно быть числом")
        amount_f = float(amount)
        if amount_f <= 0:
            raise ValidationError("'amount' должно быть положительным числом")
        self._balance += amount_f

    def withdraw(self, amount: float) -> None:
        if not isinstance(amount, (int, float)):
            raise ValidationError("'amount' должно быть числом")
        amount_f = float(amount)
        if amount_f <= 0:
            raise ValidationError("'amount' должно быть положительным числом")
        if amount_f > self._balance:
            raise InsufficientFundsError(
                f"Недостаточно средств: доступно {self._balance}, необходимо {amount_f}"
            )
        self._balance -= amount_f

    def get_balance_info(self) -> str:
        return f"{self.currency_code}: {self._balance:.4f}"


class Portfolio:
    def __init__(self, user: User, wallets: dict[str, Wallet] | None = None) -> None:
        if not isinstance(user, User):
            raise ValidationError("user должен быть зарегистрирован")
        self._user = user
        self._user_id = user.user_id
        self._wallets: dict[str, Wallet] = {}
        if wallets:
            # проверка соотвествия keys и wallet.currency_code
            for code, wallet in wallets.items():
                if not isinstance(wallet, Wallet):
                    raise ValidationError("Код валюты должен соответствовать справочнику")
                key = str(code).strip().upper()
                if not key:
                    raise ValidationError("код валюты не может быть пустым")
                self._wallets[key] = wallet

    @property
    def user(self) -> User:
        return self._user

    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def wallets(self) -> dict[str, Wallet]:
        # spec: return a copy
        return dict(self._wallets)

    def add_currency(self, currency_code: str) -> Wallet:
        if not isinstance(currency_code, str):
            raise ValidationError("currency_code должен быть string")
        code = currency_code.strip().upper()
        if not code:
            raise ValidationError("currency_code не может быть пустым")
        if code in self._wallets:
            raise ValidationError(f"кошелек '{code}' уже существует")
        wallet = Wallet(currency_code=code, balance=0.0)
        self._wallets[code] = wallet
        return wallet

    def get_wallet(self, currency_code: str) -> Wallet | None:
        code = str(currency_code).strip().upper()
        if not code:
            return None
        return self._wallets.get(code)

    def get_total_value(self, base_currency: str = "USD") -> float:
        base = str(base_currency).strip().upper()
        if not base:
            raise ValidationError("base_currency не может быть пустым")

        exchange_rates: dict[str, float] = {
            "USD_USD": 1.0,
            "EUR_USD": 1.08,
            "BTC_USD": 59337.21,
            "ETH_USD": 3720.00,
            "RUB_USD": 0.01016,
        }

        def to_usd(code: str, amount: float) -> float:
            pair = f"{code}_USD"
            rate = exchange_rates.get(pair)
            if rate is None:
                raise ValidationError(f"курс недоступен для {code}->USD")
            return amount * rate

        total_usd = 0.0
        for code, wallet in self._wallets.items():
            if code == "USD":
                total_usd += wallet.balance
            else:
                total_usd += to_usd(code, wallet.balance)

        if base == "USD":
            return total_usd

        base_pair = f"{base}_USD"
        base_rate = exchange_rates.get(base_pair)
        if base_rate is None:
            raise ValidationError(f"курс недоступен для USD->{base}")
        return total_usd / base_rate