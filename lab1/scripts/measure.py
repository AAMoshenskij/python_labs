"""Замер времени анализаторов и накладных расходов декоратора ``timed`` (углубление Core).

Запуск: ``python scripts/measure.py [rounds]``. Результат — JSON в stdout; числа зависят
от машины, поэтому в отчёт вносятся значения, полученные на вашем компьютере.
"""

from __future__ import annotations

import json
import platform
import sys
from collections.abc import Callable
from pathlib import Path
from time import perf_counter

from school_intake.analysis_service import AnalysisService
from school_intake.analyzers import AnalysisContext, Analyzer, AnalyzerRegistry
from school_intake.analyzers.length import LengthAnalyzer
from school_intake.analyzers.template import TemplateAnalyzer
from school_intake.assignments import load_assignments
from school_intake.importer import import_source
from school_intake.repository import InMemorySubmissionRepository
from school_intake.service import SubmissionService
from school_intake.sources import JSONLSource
from school_intake.utils import TimingRecorder, timed

DATA = Path(__file__).resolve().parent.parent / "data"


def timed_factory(factory: Callable[[], Analyzer], recorder: TimingRecorder) -> Callable[[], Analyzer]:
    def make() -> Analyzer:
        analyzer = factory()
        analyzer.analyze = timed(recorder)(analyzer.analyze)  # type: ignore[method-assign]
        return analyzer

    return make


def run_all(service: AnalysisService, ids: list[str], context: AnalysisContext, rounds: int) -> float:
    start = perf_counter()
    for _ in range(rounds):
        for submission_id in ids:
            for name in ("length", "template"):
                service.run(submission_id, name, context)
    return perf_counter() - start


def build(recorder: TimingRecorder | None) -> AnalysisService:
    repository = InMemorySubmissionRepository()
    registry = AnalyzerRegistry()
    for name, cls in (("length", LengthAnalyzer), ("template", TemplateAnalyzer)):
        registry.register(name, timed_factory(cls, recorder) if recorder else cls)
    return AnalysisService(repository, registry)


def main() -> None:
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
    assignment = load_assignments(DATA / "assignments.json")["assignment-01"]
    context = AnalysisContext(assignment)

    # импорт: время приёма корпуса
    repository = InMemorySubmissionRepository()
    start = perf_counter()
    summary = import_source(JSONLSource(DATA / "submissions.jsonl"), SubmissionService(repository))
    import_ms = (perf_counter() - start) * 1000
    ids = summary.accepted

    results: dict[str, object] = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "submissions": len(ids),
        "rounds": rounds,
        "import_ms": round(import_ms, 3),
    }

    plain_service = build(None)
    recorder = TimingRecorder()
    timed_service = build(recorder)
    for service in (plain_service, timed_service):
        service.repository = repository  # один и тот же корпус

    run_all(plain_service, ids, context, 50)  # прогрев
    run_all(timed_service, ids, context, 50)
    recorder.records.clear()

    calls = rounds * len(ids) * 2
    plain = run_all(plain_service, ids, context, rounds)
    with_timer = run_all(timed_service, ids, context, rounds)
    results["service_run_calls"] = calls
    results["plain_total_ms"] = round(plain * 1000, 2)
    results["timed_total_ms"] = round(with_timer * 1000, 2)
    results["plain_per_call_us"] = round(plain / calls * 1e6, 2)
    results["timed_per_call_us"] = round(with_timer / calls * 1e6, 2)
    results["decorator_overhead_us_per_call"] = round((with_timer - plain) / calls * 1e6, 2)
    results["analyze_only"] = {
        name: {k: round(v, 4) for k, v in stats.items()} for name, stats in recorder.summary().items()
    }
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
