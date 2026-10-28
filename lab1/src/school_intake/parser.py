"""Синтаксический разбор JSON отделён от проверки схемы."""

from __future__ import annotations

import json

from .errors import FormatError
from .models import Submission
from .validation import parse_submission


def _reject_repeated_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise FormatError("Повтор ключа в JSON-объекте не допускается", field=key)
        result[key] = value
    return result


def _reject_constant(value: str) -> object:
    raise FormatError(f"Нестандартное значение не допускается: {value}", field="json")


def decode_json(line: str) -> object:
    """Строгий разбор: без повторов ключей и без NaN/Infinity. Бросает FormatError."""
    try:
        return json.loads(
            line, object_pairs_hook=_reject_repeated_keys, parse_constant=_reject_constant
        )
    except json.JSONDecodeError as exc:
        raise FormatError(f"Ошибка JSON около столбца {exc.colno}", field="json") from exc
    except RecursionError as exc:
        raise FormatError("Слишком глубокая вложенность JSON", field="json") from exc


def parse_line(line: str) -> Submission:
    """JSON-строка -> Submission (FormatError либо SchemaError)."""
    return parse_submission(decode_json(line))
