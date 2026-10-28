"""Явная валидация внешних данных (единственное место проверки схемы).

Аннотации типов в рантайме ничего не проверяют, поэтому каждое поле
проверяется здесь явно, без неявных преобразований (``str(x)``, ``bool(x)``).
Входной объект не изменяется: результат — новый ``Submission``.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from .errors import SchemaError, UnsupportedVersionError
from .models import AIDeclaration, Submission

SUPPORTED_SCHEMA_VERSION = 1
SUBMISSION_FIELDS = frozenset({
    "schema_version", "submission_id", "student_id", "assignment_id", "submitted_at",
    "text", "code", "template_id", "ai_declaration",
})
DECLARATION_FIELDS = frozenset({"used", "tool", "purpose", "verified_by_student"})


def require_object(raw: object, name: str) -> dict[str, object]:
    if not isinstance(raw, dict) or any(not isinstance(key, str) for key in raw):
        raise SchemaError("Ожидается JSON-объект со строковыми ключами", field=name)
    return raw


def require_fields(raw: Mapping[str, object], expected: frozenset[str], prefix: str = "") -> None:
    """Неизвестные поля отклоняются первыми: опечатка в имени видна сразу."""
    extra = raw.keys() - expected
    if extra:
        raise SchemaError("Неизвестное поле не допускается", field=prefix + min(extra))
    missing = expected - raw.keys()
    if missing:
        raise SchemaError("Обязательное поле отсутствует", field=prefix + min(missing))


def require_string(value: object, name: str, *, nonempty: bool = True) -> str:
    if not isinstance(value, str):
        raise SchemaError("Ожидается строка без преобразования типа", field=name)
    if nonempty and not value.strip():
        raise SchemaError("Ожидается непустая строка", field=name)
    return value


def optional_string(value: object, name: str) -> str | None:
    if value is None:
        return None
    return require_string(value, name)


def require_bool(value: object, name: str) -> bool:
    if type(value) is not bool:
        raise SchemaError("Ожидается bool, а не строка или число", field=name)
    return value


def validate_timestamp(value: object) -> str:
    """ISO 8601 с часовым поясом; возвращается исходная строка."""
    text = require_string(value, "submitted_at")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise SchemaError(
            "Ожидается дата и время ISO с часовым поясом", field="submitted_at"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise SchemaError("Часовой пояс обязателен", field="submitted_at")
    return text


def parse_declaration(raw: object) -> AIDeclaration:
    data = require_object(raw, "ai_declaration")
    require_fields(data, DECLARATION_FIELDS, "ai_declaration.")
    declaration = AIDeclaration(
        used=require_bool(data["used"], "ai_declaration.used"),
        tool=optional_string(data["tool"], "ai_declaration.tool"),
        purpose=optional_string(data["purpose"], "ai_declaration.purpose"),
        verified_by_student=require_bool(
            data["verified_by_student"], "ai_declaration.verified_by_student"
        ),
    )
    if declaration.used and (declaration.tool is None or declaration.purpose is None):
        raise SchemaError("Инструмент и цель применения ИИ обязательны", field="ai_declaration")
    return declaration


def parse_submission(raw: object) -> Submission:
    """Проверяет объект и возвращает новый Submission. Бросает SchemaError."""
    data = require_object(raw, "submission")
    require_fields(data, SUBMISSION_FIELDS)

    version = data["schema_version"]
    if type(version) is not int:  # bool — подкласс int, поэтому isinstance не подходит
        raise SchemaError("Ожидается целое число; bool не допускается", field="schema_version")
    if version != SUPPORTED_SCHEMA_VERSION:
        raise UnsupportedVersionError(
            f"Поддерживается версия схемы {SUPPORTED_SCHEMA_VERSION}", field="schema_version"
        )

    declaration = parse_declaration(data["ai_declaration"])
    text = require_string(data["text"], "text", nonempty=False)
    code = require_string(data["code"], "code", nonempty=False)
    if not text.strip() and not code.strip():
        raise SchemaError("Текст или код должны быть непустыми", field="text/code")

    return Submission(
        schema_version=version,
        submission_id=require_string(data["submission_id"], "submission_id"),
        student_id=require_string(data["student_id"], "student_id"),
        assignment_id=require_string(data["assignment_id"], "assignment_id"),
        submitted_at=validate_timestamp(data["submitted_at"]),
        text=text,
        code=code,
        template_id=optional_string(data["template_id"], "template_id"),
        ai_declaration=declaration,
    )
