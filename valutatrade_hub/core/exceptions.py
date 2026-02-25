from __future__ import annotations


class ValutaTradeError(Exception):
    """Базовое исключение."""


class InsufficientFundsError(ValutaTradeError):
    def __init__(self, available: float, required: float, code: str) -> None:
        self.available = float(available)
        self.required = float(required)
        self.code = str(code).upper()
        super().__init__(
            f"Недостаточно средств: доступно {self.available:.4f} {self.code}, "
            f"необходимо {self.required:.4f} {self.code}"
        )


class CurrencyNotFoundError(ValutaTradeError):
    def __init__(self, code: str) -> None:
        self.code = str(code).upper()
        super().__init__(f"Неизвестная валюта '{self.code}'")


class ApiRequestError(ValutaTradeError):
    def __init__(self, reason: str) -> None:
        self.reason = str(reason)
        super().__init__(f"Ошибка при обращении к внешнему API: {self.reason}")