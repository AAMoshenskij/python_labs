"""Сборка отчёта и проверка результата плагина на границе."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from uuid import uuid4

from ..errors import InvalidReportError
from ..hashing import stable_hash, submission_hash
from ..models import Submission
from .base import FINDING_KINDS, AnalysisContext, AnalysisReport, Finding


def validate_report(report: AnalysisReport, value: Submission, ctx: AnalysisContext) -> None:
    """Аннотация ``-> AnalysisReport`` ничего не гарантирует, поэтому проверяем результат явно."""
    if not isinstance(report, AnalysisReport):
        raise InvalidReportError("Ожидается AnalysisReport")
    if report.submission_id != value.submission_id or report.submission_hash != submission_hash(value):
        raise InvalidReportError("Отчёт ссылается на другую версию сдачи")
    if report.config_hash != stable_hash(ctx.config_payload()):
        raise InvalidReportError("Отчёт использует другую конфигурацию")
    if not report.report_id or not report.analyzer_id or not report.analyzer_version:
        raise InvalidReportError("Идентификаторы отчёта и анализатора обязательны")
    if type(report.review_required) is not bool:
        raise InvalidReportError("review_required должен быть bool")
    try:
        created = datetime.fromisoformat(report.created_at)
    except (ValueError, TypeError) as exc:
        raise InvalidReportError("Время отчёта имеет неверный формат") from exc
    if created.tzinfo is None or created.utcoffset() is None:
        raise InvalidReportError("Часовой пояс времени отчёта обязателен")
    for finding in report.findings:
        _validate_finding(finding, value)


def _validate_finding(finding: Finding, value: Submission) -> None:
    if finding.kind not in FINDING_KINDS:
        raise InvalidReportError("Неизвестный kind")
    score = finding.score
    if score is not None and (
        type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 1
    ):
        raise InvalidReportError("score должен быть конечным числом 0–1 либо None")
    if not finding.explanation.strip():
        raise InvalidReportError("Объяснение наблюдения обязательно")
    for evidence in finding.evidence:
        if evidence.submission_id != value.submission_id or evidence.field not in ("text", "code"):
            raise InvalidReportError("Evidence ссылается на неизвестный объект или поле")
        if type(evidence.start_line) is not int or type(evidence.end_line) is not int:
            raise InvalidReportError("Номер строки должен быть int")
        line_count = len(getattr(value, evidence.field).splitlines())
        if not 1 <= evidence.start_line <= evidence.end_line <= line_count:
            raise InvalidReportError("Evidence выходит за границы исходного текста")


def make_report(
    value: Submission,
    ctx: AnalysisContext,
    analyzer_id: str,
    version: str,
    findings: tuple[Finding, ...],
    *,
    review_required: bool = False,
    report_id: str | None = None,
    created_at: datetime | None = None,
) -> AnalysisReport:
    """``report_id`` и ``created_at`` можно передать извне (воспроизводимые тесты)."""
    report = AnalysisReport(
        report_id=report_id or str(uuid4()),
        submission_id=value.submission_id,
        submission_hash=submission_hash(value),
        analyzer_id=analyzer_id,
        analyzer_version=version,
        config_hash=stable_hash(ctx.config_payload()),
        findings=findings,
        created_at=(created_at or datetime.now(UTC)).isoformat(),
        review_required=review_required,
    )
    validate_report(report, value, ctx)
    return report
