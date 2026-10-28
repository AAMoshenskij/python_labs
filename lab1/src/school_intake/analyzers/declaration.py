"""Третий анализатор для защиты: проверка непустой AI-декларации при used=true.

Не входит в реестр по умолчанию: на защите его достаточно зарегистрировать
(``registry.register("declaration", DeclarationAnalyzer)``) — центральный
сервис не меняется. Декларация — самоотчёт: она не доказывает авторство и не
является меткой происхождения текста.
"""

from __future__ import annotations

from ..models import Submission
from .base import AnalysisContext, AnalysisReport, Finding
from .reporting import make_report


def _filled(value: str | None) -> bool:
    return value is not None and bool(value.strip())


class DeclarationAnalyzer:
    analyzer_id = "declaration"
    analyzer_version = "1.0"

    def analyze(self, submission: Submission, context: AnalysisContext) -> AnalysisReport:
        declaration = submission.ai_declaration
        review_required = False
        if not declaration.used:
            explanation = (
                "Использование ИИ не заявлено. Авторство текста автоматически не определялось."
            )
        elif _filled(declaration.tool) and _filled(declaration.purpose):
            explanation = (
                f"Использование ИИ заявлено. Инструмент: {declaration.tool}; "
                f"цель: {declaration.purpose}."
            )
            review_required = not declaration.verified_by_student
        else:
            explanation = (
                "Заявлено использование ИИ (used=true), но инструмент или цель не заполнены."
            )
            review_required = True
        finding = Finding("rubric_feedback", None, (), explanation)
        return make_report(
            submission,
            context,
            self.analyzer_id,
            self.analyzer_version,
            (finding,),
            review_required=review_required,
        )
