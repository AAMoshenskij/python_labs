"""TemplateAnalyzer: точные блоки строк разрешённого шаблона в code.

Сравнение без нормализации пробелов; завершающий перевод строки не создаёт
лишней строки (``splitlines``). Номера строк относятся к исходному ``code``.
Нечёткое сходство и AST-анализ не выполняются, плагиат не доказывается.
"""

from __future__ import annotations

from ..errors import AnalysisFailure
from ..models import Submission
from .base import AnalysisContext, AnalysisReport, Evidence, Finding
from .reporting import make_report


def template_ranges(source_code: str, template: str) -> tuple[tuple[int, int], ...]:
    if not template.strip():
        return ()  # пустой шаблон не считается совпадением со всем файлом
    source_lines = source_code.splitlines()
    template_lines = template.splitlines()
    width = len(template_lines)
    return tuple(
        (index + 1, index + width)
        for index in range(len(source_lines) - width + 1)
        if source_lines[index : index + width] == template_lines
    )


class TemplateAnalyzer:
    analyzer_id = "template"
    analyzer_version = "1.0"

    def analyze(self, submission: Submission, context: AnalysisContext) -> AnalysisReport:
        if submission.assignment_id != context.assignment.assignment_id:
            raise AnalysisFailure("Контекст относится к другому заданию", field="assignment_id")
        ranges = template_ranges(submission.code, context.assignment.allowed_template)
        evidence = tuple(
            Evidence(submission.submission_id, "code", start, end) for start, end in ranges
        )
        explanation = (
            f"Найдены разрешённые блоки шаблона: {len(ranges)}. "
            "Это допустимое совпадение, а не основание санкции."
            if ranges
            else "Точное совпадение с разрешённым шаблоном не найдено. "
            "Нечёткое сходство не проверялось."
        )
        finding = Finding("similarity", None, evidence, explanation)
        return make_report(
            submission, context, self.analyzer_id, self.analyzer_version, (finding,)
        )
