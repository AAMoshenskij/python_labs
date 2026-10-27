"""Неизменяемые модели данных.

``frozen=True`` запрещает присваивание атрибутов, но не замораживает вложенные
изменяемые объекты; поэтому все поля здесь — строки, числа, bool и кортежи.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AIDeclaration:
    used: bool
    tool: str | None
    purpose: str | None
    verified_by_student: bool


@dataclass(frozen=True, slots=True)
class Submission:
    """Одна версия сдачи. Новая версия работы имеет новый submission_id."""

    schema_version: int
    submission_id: str
    student_id: str
    assignment_id: str
    submitted_at: str  # исходное представление из валидного JSON
    text: str
    code: str
    template_id: str | None
    ai_declaration: AIDeclaration


@dataclass(frozen=True, slots=True)
class Assignment:
    assignment_id: str
    allowed_template: str
    requirements: tuple[str, ...] = ()
