"""Контракт источника сдач.

Источник владеет ресурсом: ``open()`` возвращает контекстный менеджер, который
выдаёт итератор записей, а выход из ``with`` освобождает ресурс — при полном
чтении, раннем ``break`` и исключении потребителя. Использовать итератор после
выхода из контекста нельзя.

``Protocol`` описывает структуру: независимый класс с таким методом подходит
без наследования (в отличие от ABC, где важна принадлежность иерархии).
Совместимость сигнатуры не гарантирует закрытие файла — это проверяют
контрактные тесты.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Protocol

from ..errors import FormatError


@dataclass(frozen=True, slots=True)
class SourceRecord:
    """Запись источника. line_no начинается с 1; схему проверяет parser, не источник."""

    line_no: int
    raw: object = None
    error: FormatError | None = None


class SubmissionSource(Protocol):
    def open(self) -> AbstractContextManager[Iterator[SourceRecord]]: ...
