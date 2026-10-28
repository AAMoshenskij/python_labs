"""Импорт источника с частичным успехом: атомарность на уровне одной сдачи."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .errors import IntakeError
from .service import SubmissionService
from .sources.base import SubmissionSource


@dataclass
class ImportSummary:
    accepted: list[str] = field(default_factory=list)
    duplicate: list[str] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def import_source(source: SubmissionSource, service: SubmissionService) -> ImportSummary:
    """Ошибка строки попадает в errors (с line_no) и не останавливает импорт.

    Неожиданные исключения (не IntakeError) намеренно не перехватываются.
    """
    summary = ImportSummary()
    with source.open() as records:
        for record in records:
            if record.error is not None:
                summary.errors.append({"line_no": record.line_no, **record.error.to_dict()})
                continue
            try:
                result = service.accept(record.raw)
            except IntakeError as exc:
                summary.errors.append({"line_no": record.line_no, **exc.to_dict()})
            else:
                target = summary.accepted if result.status == "accepted" else summary.duplicate
                target.append(result.submission_id)
    return summary
