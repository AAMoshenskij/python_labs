from __future__ import annotations

import pytest

from conftest import ASSIGNMENT
from school_intake.analyzers import AnalysisContext, LengthAnalyzer
from school_intake.models import Submission
from school_intake.utils import TimingRecorder, timed


def test_timed_preserves_metadata_result_and_records() -> None:
    recorder = TimingRecorder()

    @timed(recorder)
    def add(a: int, b: int = 1) -> int:
        """Складывает."""
        return a + b

    assert add(2, b=3) == 5
    assert add.__name__ == "add" and add.__doc__ == "Складывает."
    assert add.__wrapped__(1, 1) == 2  # type: ignore[attr-defined]
    assert len(recorder.records["test_timed_preserves_metadata_result_and_records.<locals>.add"]) == 1


def test_timed_records_failed_calls_and_keeps_exception() -> None:
    recorder = TimingRecorder()

    @timed(recorder)
    def fail() -> None:
        raise ValueError("сбой")

    with pytest.raises(ValueError, match="сбой"):
        fail()
    assert sum(len(v) for v in recorder.records.values()) == 1


def test_timed_wraps_analyzer_method_without_changing_report(submission: Submission) -> None:
    recorder = TimingRecorder()
    analyzer = LengthAnalyzer()
    analyzer.analyze = timed(recorder)(analyzer.analyze)  # type: ignore[method-assign]
    report = analyzer.analyze(submission, AnalysisContext(ASSIGNMENT))
    assert report.analyzer_id == "length"
    stats = recorder.summary()["LengthAnalyzer.analyze"]
    assert stats["calls"] == 1.0 and stats["max_ms"] >= 0.0
