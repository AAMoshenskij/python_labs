"""CLI: ``school-intake import FILE`` и ``school-intake analyze FILE --assignments FILE``.

CLI отвечает за аргументы, выбор адаптера, формат вывода и код завершения;
валидация и хранение остаются в общих компонентах.

Код завершения: 0 — успех; 1 — ошибки отдельных строк или анализа; 2 — источник
недоступен. Машинный JSON — в stdout, диагностика — в stderr. Состояние
in-memory исчезает вместе с процессом.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .analysis_service import AnalysisService
from .analyzers import AnalysisContext, default_registry
from .assignments import load_assignments
from .errors import AnalysisFailure, SchemaError
from .importer import import_source
from .plugins import load_plugins
from .repository import InMemorySubmissionRepository
from .service import SubmissionService
from .sources import JSONLSource

DEFAULT_ANALYZERS = ("length", "template")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="school-intake", description="Приём учебных сдач из JSONL")
    sub = parser.add_subparsers(dest="command", required=True)

    imp = sub.add_parser("import", help="импорт файла сдач")
    imp.add_argument("path", type=Path)

    ana = sub.add_parser("analyze", help="импорт и запуск анализаторов")
    ana.add_argument("path", type=Path)
    ana.add_argument("--assignments", type=Path, required=True, help="assignments.json")
    ana.add_argument("--analyzers", nargs="+", default=list(DEFAULT_ANALYZERS))
    ana.add_argument("--no-plugins", action="store_true", help="не загружать entry points")
    return parser


def _fail(code: str, message: str) -> int:
    print(json.dumps({"code": code, "message": message}, ensure_ascii=False), file=sys.stderr)
    return 2


def _cmd_import(args: argparse.Namespace) -> int:
    service = SubmissionService(InMemorySubmissionRepository())
    try:
        summary = import_source(JSONLSource(args.path), service)
    except (OSError, UnicodeError) as exc:
        return _fail("source_unavailable", str(exc))
    print(json.dumps(summary.to_dict(), ensure_ascii=False))
    return 1 if summary.errors else 0


def _cmd_analyze(args: argparse.Namespace) -> int:
    try:
        assignments = load_assignments(args.assignments)
    except (OSError, ValueError, SchemaError) as exc:
        return _fail("assignments_unavailable", str(exc))

    registry = default_registry()
    if not args.no_plugins:
        try:
            load_plugins(registry)
        except AnalysisFailure as exc:
            return _fail(exc.code, exc.message)

    repository = InMemorySubmissionRepository()
    try:
        summary = import_source(JSONLSource(args.path), SubmissionService(repository))
    except (OSError, UnicodeError) as exc:
        return _fail("source_unavailable", str(exc))

    service = AnalysisService(repository, registry)
    reports: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for submission_id in summary.accepted:
        submission = repository.get(submission_id)
        assert submission is not None
        assignment = assignments.get(submission.assignment_id)
        if assignment is None:
            failures.append({
                "submission_id": submission_id, "code": "unknown_assignment",
                "field": "assignment_id", "message": "Задание не найдено в assignments.json",
            })
            continue
        context = AnalysisContext(assignment)
        for name in args.analyzers:
            try:
                reports.append(asdict(service.run(submission_id, name, context)))
            except AnalysisFailure as exc:
                failures.append({"submission_id": submission_id, "analyzer": name, **exc.to_dict()})

    payload = {"import": summary.to_dict(), "reports": reports, "failures": failures}
    print(json.dumps(payload, ensure_ascii=False))
    return 1 if summary.errors or failures else 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "import":
        return _cmd_import(args)
    return _cmd_analyze(args)


def entry() -> None:
    """Точка входа console script: UTF-8 для потоков (консоль Windows) и код завершения."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())


if __name__ == "__main__":  # pragma: no cover
    entry()
