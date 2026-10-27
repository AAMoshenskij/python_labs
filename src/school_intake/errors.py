"""Исключения домена.

У каждой ошибки есть машиночитаемый ``code``, имя поля ``field`` и понятное
``message``. Выбор HTTP-статуса или кода завершения CLI относится к адаптерам.
"""

from __future__ import annotations


class DomainError(Exception):
    code: str = "domain_error"

    def __init__(self, message: str, *, field: str = "", code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code
        self.field = field
        self.message = message

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "field": self.field, "message": self.message}

    def __str__(self) -> str:
        where = f" [{self.field}]" if self.field else ""
        return f"{self.code}{where}: {self.message}"


# --- приём (этап А) -----------------------------------------------------------


class IntakeError(DomainError):
    code = "intake_error"


class FormatError(IntakeError):
    """Строка не является допустимым JSON (синтаксис, повтор ключа, NaN)."""

    code = "invalid_json"


class SchemaError(IntakeError):
    """JSON корректен, но нарушает схему Submission."""

    code = "schema_error"


class UnsupportedVersionError(SchemaError):
    code = "unsupported_version"


class ConflictError(IntakeError):
    """Тот же submission_id, но другое содержимое."""

    code = "conflict"


# --- анализ (этап Б) ----------------------------------------------------------


class AnalysisFailure(DomainError):
    """Анализ не выполнен или результат анализатора нарушает контракт."""

    code = "analysis_failure"


class UnknownAnalyzerError(AnalysisFailure):
    code = "unknown_analyzer"


class InvalidReportError(AnalysisFailure):
    code = "invalid_report"


class AnalyzerCrashedError(AnalysisFailure):
    """Анализатор завершился неожиданным исключением (причина — в __cause__)."""

    code = "analyzer_crashed"


class PluginLoadError(AnalysisFailure):
    code = "plugin_load_failed"
