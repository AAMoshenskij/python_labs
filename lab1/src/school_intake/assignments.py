"""Загрузка assignments.json: список заданий (или объект с ключом ``assignments``).

Поля задания: ``assignment_id``, ``allowed_template`` (строка), ``requirements`` (список строк).
"""

from __future__ import annotations

import json
from pathlib import Path

from .errors import SchemaError
from .models import Assignment
from .validation import require_fields, require_object, require_string

_FIELDS = frozenset({"assignment_id", "allowed_template", "requirements"})


def _parse_assignment(raw: object) -> Assignment:
    data = require_object(raw, "assignment")
    require_fields(data, _FIELDS)
    requirements = data["requirements"]
    if not isinstance(requirements, list):
        raise SchemaError("Ожидается список строк", field="requirements")
    return Assignment(
        assignment_id=require_string(data["assignment_id"], "assignment_id"),
        allowed_template=require_string(data["allowed_template"], "allowed_template", nonempty=False),
        requirements=tuple(
            require_string(item, "requirements", nonempty=False) for item in requirements
        ),
    )


def load_assignments(path: str | Path) -> dict[str, Assignment]:
    """OSError и ValueError (битый JSON) пробрасываются; нарушение схемы — SchemaError."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict) and "assignments" in data:
        data = data["assignments"]
    if not isinstance(data, list):
        raise SchemaError("Ожидается список заданий", field="assignments")
    result: dict[str, Assignment] = {}
    for item in data:
        assignment = _parse_assignment(item)
        if assignment.assignment_id in result:
            raise SchemaError("Повтор assignment_id", field="assignment_id")
        result[assignment.assignment_id] = assignment
    return result
