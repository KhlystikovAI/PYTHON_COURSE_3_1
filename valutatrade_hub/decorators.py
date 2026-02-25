from __future__ import annotations

import functools
import logging
from typing import Any, Callable, TypeVar

logger = logging.getLogger("valutatrade")

F = TypeVar("F", bound=Callable[..., Any])


def log_action(action: str, verbose: bool = False) -> Callable[[F], F]:
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # исходя из ТЗ: user_id / username / currency_code / amount / rate / base
            try:
                result = func(*args, **kwargs)
                logger.info(
                    "%s user_id=%s username=%s currency=%s amount=%s base=%s rate=%s result=OK%s",
                    action,
                    kwargs.get("user_id"),
                    kwargs.get("username"),
                    kwargs.get("currency_code") or kwargs.get("currency"),
                    kwargs.get("amount"),
                    kwargs.get("base"),
                    kwargs.get("rate"),
                    f" details={result}" if verbose else "",
                )
                return result
            except Exception as e:
                logger.info(
                    "%s user_id=%s username=%s currency=%s amount=%s base=%s result=ERROR error_type=%s error=%s",
                    action,
                    kwargs.get("user_id"),
                    kwargs.get("username"),
                    kwargs.get("currency_code") or kwargs.get("currency"),
                    kwargs.get("amount"),
                    kwargs.get("base"),
                    type(e).__name__,
                    str(e),
                )
                raise

        return wrapper  

    return decorator