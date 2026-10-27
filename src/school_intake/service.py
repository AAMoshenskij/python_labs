"""Сервис приёма. Не читает stdin и не обращается к HTTP."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .errors import ConflictError
from .hashing import submission_hash
from .models import Submission
from .parser import decode_json
from .repository import SubmissionRepository
from .validation import parse_submission


@dataclass(frozen=True, slots=True)
class Acceptance:
    status: Literal["accepted", "duplicate"]
    submission: Submission  # при duplicate — уже принятая сдача
    content_hash: str

    @property
    def submission_id(self) -> str:
        return self.submission.submission_id


class SubmissionService:
    def __init__(self, repository: SubmissionRepository) -> None:
        self.repository = repository

    def accept(self, raw: object) -> Acceptance:
        """Новая сдача -> accepted; тот же id и хеш -> duplicate; иначе ConflictError."""
        value = parse_submission(raw)  # проверка предшествует любому изменению состояния
        digest = submission_hash(value)
        previous = self.repository.get(value.submission_id)
        if previous is None:
            self.repository.add(value)
            return Acceptance("accepted", value, digest)
        if submission_hash(previous) != digest:
            raise ConflictError(
                "Для новой версии работы требуется новый submission_id", field="submission_id"
            )
        return Acceptance("duplicate", previous, digest)

    def accept_line(self, line: str) -> Acceptance:
        """Принимает одну JSONL-строку (без CLI и файлов)."""
        return self.accept(decode_json(line))
