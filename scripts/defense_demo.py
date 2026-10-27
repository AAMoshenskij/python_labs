"""Сценарий защиты: импорт, конфликт, ошибочная строка и третий анализатор без правки сервиса.

Запуск: ``python scripts/defense_demo.py``
"""

from __future__ import annotations

import json
from pathlib import Path

from school_intake.analysis_service import AnalysisService
from school_intake.analyzers import AnalysisContext, DeclarationAnalyzer, default_registry
from school_intake.assignments import load_assignments
from school_intake.errors import UnknownAnalyzerError
from school_intake.importer import import_source
from school_intake.repository import InMemorySubmissionRepository
from school_intake.service import SubmissionService
from school_intake.sources import InMemorySource, JSONLSource

DATA = Path(__file__).resolve().parent.parent / "data"


def show(title: str, value: object) -> None:
    print(f"\n=== {title}")
    print(json.dumps(value, ensure_ascii=False, indent=2))


def main() -> None:
    repository = InMemorySubmissionRepository()
    intake = SubmissionService(repository)

    # 1. Успешный импорт
    summary = import_source(JSONLSource(DATA / "submissions.jsonl"), intake)
    show("Успешный импорт", {"accepted": len(summary.accepted), "errors": summary.errors})

    # 2. Повторный импорт: только duplicate
    again = import_source(JSONLSource(DATA / "submissions.jsonl"), intake)
    show("Повторный импорт", {"duplicate": len(again.duplicate), "accepted": len(again.accepted)})

    # 3. Конфликт идентификатора и ошибочные строки; исходная сдача не перезаписана
    original = repository.get("sub-001")
    broken = import_source(
        InMemorySource([
            {**json.loads((DATA / "submissions.jsonl").read_text("utf-8").splitlines()[0]),
             "text": "Другое содержимое с тем же ID"},
            {"submission_id": "x"},
        ]),
        intake,
    )
    show("Конфликт и ошибка схемы", broken.errors)
    assert repository.get("sub-001") is original

    # 4. Третий анализатор подключается регистрацией; AnalysisService не меняется
    registry = default_registry()
    service = AnalysisService(repository, registry)
    context = AnalysisContext(load_assignments(DATA / "assignments.json")["assignment-01"])
    try:
        service.run("sub-003", "declaration", context)
    except UnknownAnalyzerError as exc:
        show("До регистрации", exc.to_dict())
    registry.register("declaration", DeclarationAnalyzer)
    report = service.run("sub-003", "declaration", context)
    show("После регистрации", [f.explanation for f in report.findings])


if __name__ == "__main__":
    main()
