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


class AuthError(RuntimeError):
    """Используется login/register ошибок."""


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
        raise AuthError("Хранилище users.json повреждено")

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
        raise AuthError("Хранилище portfolios.json повреждено")

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
        raise AuthError("Хранилище users.json повреждено")

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