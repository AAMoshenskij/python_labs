"""Контракт анализатора и модели отчёта (синхронно; конкурентный адаптер — в ЛР 3)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal, Protocol

from ..models import Assignment, Submission

FindingKind = Literal["similarity", "rubric_feedback", "processing_error"]
FINDING_KINDS: frozenset[str] = frozenset({"similarity", "rubric_feedback", "processing_error"})


@dataclass(frozen=True, slots=True)
class Evidence:
    """Включительный диапазон строк (с 1) в ИСХОДНОМ поле text или code."""

    submission_id: str
    field: Literal["text", "code"]
    start_line: int
    end_line: int


@dataclass(frozen=True, slots=True)
class Finding:
    kind: FindingKind
    score: float | None  # конечное число 0..1 либо None (нет обоснованной метрики)
    evidence: tuple[Evidence, ...]
    explanation: str


@dataclass(frozen=True, slots=True)
class AnalysisReport:
    report_id: str  # идентификатор запуска, не содержимого
    submission_id: str
    submission_hash: str
    analyzer_id: str
    analyzer_version: str
    config_hash: str
    findings: tuple[Finding, ...]
    created_at: str
    review_required: bool


@dataclass(frozen=True, slots=True)
class AnalysisContext:
    """Требования задания и явная неизменяемая конфигурация."""

    assignment: Assignment
    mode: Literal["baseline", "stub"] = "baseline"
    config_version: str = "1"

    def config_payload(self) -> dict[str, object]:
        return {
            "assignment": asdict(self.assignment),
            "mode": self.mode,
            "config_version": self.config_version,
        }


class Analyzer(Protocol):
    @property
    def analyzer_id(self) -> str: ...

    @property
    def analyzer_version(self) -> str: ...

    def analyze(self, submission: Submission, context: AnalysisContext) -> AnalysisReport: ...
