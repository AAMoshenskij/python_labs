"""Репозиторий сдач: интерфейс (Protocol) и in-memory реализация."""

from __future__ import annotations

from typing import Protocol

from .errors import ConflictError
from .models import Submission


class SubmissionRepository(Protocol):
    def get(self, submission_id: str) -> Submission | None: ...

    def add(self, submission: Submission) -> None: ...


class InMemorySubmissionRepository:
    def __init__(self) -> None:
        self._items: dict[str, Submission] = {}

    def get(self, submission_id: str) -> Submission | None:
        return self._items.get(submission_id)

    def add(self, submission: Submission) -> None:
        if submission.submission_id in self._items:
            raise ConflictError("Идентификатор уже сохранён", field="submission_id")
        self._items[submission.submission_id] = submission

    def __len__(self) -> int:
        return len(self._items)
