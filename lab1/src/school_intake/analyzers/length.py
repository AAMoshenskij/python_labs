"""LengthAnalyzer: считает непустые строки text и code. Качество решения не оценивает."""

from __future__ import annotations

from ..models import Submission
from .base import AnalysisContext, AnalysisReport, Evidence, Finding
from .reporting import make_report


def nonempty_line_numbers(text: str) -> tuple[int, ...]:
    """Номера (с 1) непустых строк в исходном тексте; сам текст не изменяется."""
    return tuple(number for number, line in enumerate(text.splitlines(), 1) if line.strip())


class LengthAnalyzer:
    analyzer_id = "length"
    analyzer_version = "1.0"

    def analyze(self, submission: Submission, context: AnalysisContext) -> AnalysisReport:
        text_lines = nonempty_line_numbers(submission.text)
        code_lines = nonempty_line_numbers(submission.code)
        evidence = (
            *(Evidence(submission.submission_id, "text", n, n) for n in text_lines),
            *(Evidence(submission.submission_id, "code", n, n) for n in code_lines),
        )
        finding = Finding(
            kind="rubric_feedback",
            score=None,
            evidence=evidence,
            explanation=(
                f"Непустые строки: text={len(text_lines)}, code={len(code_lines)}. "
                "Длина не оценивает корректность решения."
            ),
        )
        return make_report(
            submission, context, self.analyzer_id, self.analyzer_version, (finding,)
        )
