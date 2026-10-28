"""Центральный сервис анализа.

Выбирает анализатор по реестру и не знает конкретных классов: новый анализатор
подключается регистрацией, без ветвления ``if name == ...``.
"""

from __future__ import annotations

from .analyzers.base import AnalysisContext, AnalysisReport
from .analyzers.registry import AnalyzerRegistry
from .analyzers.reporting import validate_report
from .errors import AnalysisFailure, AnalyzerCrashedError
from .repository import SubmissionRepository


class AnalysisService:
    def __init__(self, repository: SubmissionRepository, registry: AnalyzerRegistry) -> None:
        self.repository = repository
        self.registry = registry

    def run(
        self, submission_id: str, analyzer_name: str, context: AnalysisContext
    ) -> AnalysisReport:
        value = self.repository.get(submission_id)
        if value is None:
            raise AnalysisFailure("Анализ возможен после приёма сдачи", field="submission_id")
        if value.assignment_id != context.assignment.assignment_id:
            raise AnalysisFailure("Требуется контекст соответствующего задания", field="assignment_id")
        analyzer = self.registry.create(analyzer_name)
        try:
            report = analyzer.analyze(value, context)
        except AnalysisFailure:
            raise
        except Exception as exc:  # граница плагина: причина сохраняется в __cause__
            raise AnalyzerCrashedError(
                f"Анализатор {analyzer_name!r} завершился ошибкой: {exc}", field="analyzer_id"
            ) from exc
        validate_report(report, value, context)
        if report.analyzer_id != analyzer.analyzer_id or report.analyzer_version != analyzer.analyzer_version:
            raise AnalysisFailure("Отчёт не соответствует вызванному анализатору", field="analyzer_id")
        return report
