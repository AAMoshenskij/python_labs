"""Контрактные тесты анализаторов и проверка результата плагина на границе."""

from __future__ import annotations

import copy
import dataclasses
import math
from collections.abc import Callable
from datetime import UTC

import pytest

from conftest import ASSIGNMENT, changed
from school_intake.analysis_service import AnalysisService
from school_intake.analyzers import (
    AnalysisContext,
    AnalysisReport,
    Analyzer,
    AnalyzerRegistry,
    DeclarationAnalyzer,
    Evidence,
    Finding,
    LengthAnalyzer,
    TemplateAnalyzer,
    default_registry,
    make_report,
    validate_report,
)
from school_intake.analyzers.length import nonempty_line_numbers
from school_intake.analyzers.template import template_ranges
from school_intake.errors import (
    AnalysisFailure,
    AnalyzerCrashedError,
    InvalidReportError,
    UnknownAnalyzerError,
)
from school_intake.hashing import stable_hash
from school_intake.models import AIDeclaration, Assignment, Submission
from school_intake.repository import InMemorySubmissionRepository
from school_intake.validation import parse_submission

ANALYZERS: list[Callable[[], Analyzer]] = [LengthAnalyzer, TemplateAnalyzer, DeclarationAnalyzer]
ids = ["length", "template", "declaration"]

SUBMISSIONS: list[Submission] = [
    parse_submission(changed()),
    parse_submission(changed(text="", code="x = 1\r\n\r\n  y = 2\n")),
    parse_submission(changed(text="только текст\n\n", code="")),
    parse_submission(changed(code="# Только комментарий\n", template_id=None)),
    parse_submission(changed(ai_declaration={
        "used": True, "tool": "помощник", "purpose": "обсуждение", "verified_by_student": False})),
]


@pytest.mark.parametrize("factory", ANALYZERS, ids=ids)
@pytest.mark.parametrize("submission", SUBMISSIONS, ids=range(len(SUBMISSIONS)))
def test_report_contract(
    factory: Callable[[], Analyzer], submission: Submission, context: AnalysisContext
) -> None:
    analyzer = factory()
    before = copy.deepcopy(submission)
    first = analyzer.analyze(submission, context)
    second = analyzer.analyze(submission, context)

    validate_report(first, submission, context)
    assert first.analyzer_id == analyzer.analyzer_id
    assert first.analyzer_version == analyzer.analyzer_version
    assert first.submission_id == submission.submission_id
    assert first.findings and all(f.explanation.strip() for f in first.findings)
    assert first.findings == second.findings  # смысловой результат повторяем
    assert first.submission_hash == second.submission_hash
    assert first.config_hash == second.config_hash
    assert first.report_id != second.report_id  # id идентифицирует запуск
    assert submission == before  # исходный объект не изменён
    for finding in first.findings:
        for ev in finding.evidence:  # диапазоны относятся к исходному содержимому
            lines = getattr(submission, ev.field).splitlines()
            assert 1 <= ev.start_line <= ev.end_line <= len(lines)


# --- LengthAnalyzer -----------------------------------------------------------


def test_nonempty_line_numbers_use_original_numbering() -> None:
    assert nonempty_line_numbers("\n a \n\n b\n") == (2, 4)
    assert nonempty_line_numbers("") == ()


def test_length_counts_text_and_code_separately(context: AnalysisContext) -> None:
    report = LengthAnalyzer().analyze(parse_submission(changed()), context)
    finding = report.findings[0]
    assert finding.kind == "rubric_feedback" and finding.score is None
    assert "text=1, code=3" in finding.explanation
    assert [(e.field, e.start_line) for e in finding.evidence] == [
        ("text", 1), ("code", 1), ("code", 3), ("code", 4)
    ]


def test_length_evidence_numbers_skip_blank_lines(context: AnalysisContext) -> None:
    sub = parse_submission(changed(text="", code="\n\nx\n\ny\n"))
    report = LengthAnalyzer().analyze(sub, context)
    assert [e.start_line for e in report.findings[0].evidence] == [3, 5]


# --- TemplateAnalyzer ---------------------------------------------------------


def test_template_ranges_cases() -> None:
    assert template_ranges("a\nb\na\nb\n", "a\nb\n") == ((1, 2), (3, 4))  # два совпадения
    assert template_ranges("a\n b\n", "a\nb\n") == ()  # изменён пробел
    assert template_ranges("x\ny\n", "a\nb\n") == ()  # нет совпадений
    assert template_ranges("a\n", " \n") == ()  # пустой шаблон
    assert template_ranges("a\n", "a\nb\n") == ()  # шаблон длиннее кода
    assert template_ranges("pre\na\nb\npost", "a\nb") == ((2, 3),)  # без завершающего \n


def test_template_evidence_has_original_line_numbers(context: AnalysisContext) -> None:
    sub = parse_submission(changed(code="x\n\nfrom typing import Iterable\ny\n"))
    report = TemplateAnalyzer().analyze(sub, context)
    finding = report.findings[0]
    assert [(e.field, e.start_line, e.end_line) for e in finding.evidence] == [("code", 3, 3)]
    assert finding.kind == "similarity" and finding.score is None
    assert "допустимое совпадение" in finding.explanation


def test_template_without_match_says_fuzzy_not_checked(context: AnalysisContext) -> None:
    sub = parse_submission(changed(code="def solve(values): return 0\n"))
    explanation = TemplateAnalyzer().analyze(sub, context).findings[0].explanation
    assert "не найдено" in explanation and "Нечёткое сходство не проверялось" in explanation


def test_template_rejects_context_of_other_assignment(submission: Submission) -> None:
    other = AnalysisContext(Assignment("assignment-02", "x\n"))
    with pytest.raises(AnalysisFailure):
        TemplateAnalyzer().analyze(submission, other)


# --- DeclarationAnalyzer ------------------------------------------------------


def test_declaration_not_used(submission: Submission, context: AnalysisContext) -> None:
    report = DeclarationAnalyzer().analyze(submission, context)
    assert "не заявлено" in report.findings[0].explanation and not report.review_required


def test_declaration_used_unverified_requires_review(context: AnalysisContext) -> None:
    report = DeclarationAnalyzer().analyze(SUBMISSIONS[-1], context)
    assert "заявлено" in report.findings[0].explanation and report.review_required


def test_declaration_detects_empty_fields_even_if_parser_was_bypassed(
    submission: Submission, context: AnalysisContext
) -> None:
    broken = dataclasses.replace(
        submission, ai_declaration=AIDeclaration(True, "  ", None, True)
    )
    report = DeclarationAnalyzer().analyze(broken, context)
    assert "не заполнены" in report.findings[0].explanation and report.review_required


# --- validate_report ----------------------------------------------------------


def good_report(submission: Submission, context: AnalysisContext) -> AnalysisReport:
    return LengthAnalyzer().analyze(submission, context)


@pytest.mark.parametrize("score", [True, float("nan"), float("inf"), 1.5, -0.1, "0.5"])
def test_invalid_score_rejected(score: object, submission: Submission, context: AnalysisContext) -> None:
    good = good_report(submission, context)
    bad_finding = dataclasses.replace(good.findings[0], score=score)  # type: ignore[arg-type]
    with pytest.raises(InvalidReportError):
        validate_report(dataclasses.replace(good, findings=(bad_finding,)), submission, context)


@pytest.mark.parametrize("score", [None, 0, 0.0, 0.5, 1, 1.0])
def test_valid_score_accepted(score: float | None, submission: Submission, context: AnalysisContext) -> None:
    good = good_report(submission, context)
    finding = dataclasses.replace(good.findings[0], score=score)
    validate_report(dataclasses.replace(good, findings=(finding,)), submission, context)
    assert not (isinstance(score, float) and math.isnan(score))


@pytest.mark.parametrize(
    "evidence",
    [
        Evidence("sub-001", "code", 0, 1),      # строка 0
        Evidence("sub-001", "code", 3, 2),      # начало после конца
        Evidence("sub-001", "code", 1, 99),     # за границей
        Evidence("sub-001", "diff", 1, 1),      # type: ignore[arg-type]  # нет такого поля
        Evidence("другая", "code", 1, 1),       # чужая сдача
        Evidence("sub-001", "code", True, 1),   # type: ignore[arg-type]  # bool вместо int
    ],
)
def test_invalid_evidence_rejected(
    evidence: Evidence, submission: Submission, context: AnalysisContext
) -> None:
    good = good_report(submission, context)
    finding = Finding("rubric_feedback", None, (evidence,), "объяснение")
    with pytest.raises(InvalidReportError):
        validate_report(dataclasses.replace(good, findings=(finding,)), submission, context)


@pytest.mark.parametrize(
    "mutation",
    [
        {"submission_hash": "incorrect"},
        {"submission_id": "чужая"},
        {"config_hash": "incorrect"},
        {"report_id": ""},
        {"analyzer_version": ""},
        {"review_required": "false"},
        {"created_at": "вчера"},
        {"created_at": "2026-09-01T10:00:00"},
    ],
)
def test_invalid_report_fields_rejected(
    mutation: dict[str, object], submission: Submission, context: AnalysisContext
) -> None:
    bad = dataclasses.replace(good_report(submission, context), **mutation)  # type: ignore[arg-type]
    with pytest.raises(InvalidReportError):
        validate_report(bad, submission, context)


def test_empty_explanation_and_unknown_kind_rejected(
    submission: Submission, context: AnalysisContext
) -> None:
    good = good_report(submission, context)
    for finding in (
        dataclasses.replace(good.findings[0], explanation="  "),
        dataclasses.replace(good.findings[0], kind="verdict"),  # type: ignore[arg-type]
    ):
        with pytest.raises(InvalidReportError):
            validate_report(dataclasses.replace(good, findings=(finding,)), submission, context)


def test_report_for_other_version_of_submission_rejected(
    submission: Submission, context: AnalysisContext
) -> None:
    report = good_report(submission, context)
    edited = dataclasses.replace(submission, code=submission.code + "# правка\n")
    with pytest.raises(InvalidReportError):
        validate_report(report, edited, context)


def test_make_report_accepts_injected_id_and_clock(
    submission: Submission, context: AnalysisContext
) -> None:
    from datetime import datetime

    moment = datetime(2026, 9, 1, tzinfo=UTC)
    kwargs = {"report_id": "fixed", "created_at": moment}
    a = make_report(submission, context, "x", "1", (Finding("rubric_feedback", None, (), "о"),), **kwargs)  # type: ignore[arg-type]
    b = make_report(submission, context, "x", "1", (Finding("rubric_feedback", None, (), "о"),), **kwargs)  # type: ignore[arg-type]
    assert a == b


# --- config_hash --------------------------------------------------------------


def test_config_hash_changes_with_version_and_template(submission: Submission) -> None:
    base = AnalysisContext(ASSIGNMENT)
    other_version = dataclasses.replace(base, config_version="2")
    other_template = AnalysisContext(Assignment("assignment-01", "import os\n"))
    hashes = {stable_hash(c.config_payload()) for c in (base, other_version, other_template)}
    assert len(hashes) == 3
    old = LengthAnalyzer().analyze(submission, base)
    with pytest.raises(InvalidReportError):  # прежний отчёт — не результат новой конфигурации
        validate_report(old, submission, other_version)


# --- реестр и сервис ----------------------------------------------------------


class BrokenAnalyzer:
    analyzer_id = "broken"
    analyzer_version = "1.0"

    def analyze(self, submission: Submission, context: AnalysisContext) -> AnalysisReport:
        good = LengthAnalyzer().analyze(submission, context)
        return dataclasses.replace(good, submission_hash="incorrect")


class CrashingAnalyzer:
    analyzer_id = "crash"
    analyzer_version = "1.0"

    def analyze(self, submission: Submission, context: AnalysisContext) -> AnalysisReport:
        raise ZeroDivisionError("внутренний дефект")


class MislabeledAnalyzer(LengthAnalyzer):
    analyzer_id = "other-name"


def test_registry_rejects_duplicate_and_blank_names() -> None:
    registry = default_registry()
    with pytest.raises(AnalysisFailure):
        registry.register("length", LengthAnalyzer)
    with pytest.raises(AnalysisFailure):
        registry.register("  ", LengthAnalyzer)


def test_registry_unknown_name() -> None:
    with pytest.raises(UnknownAnalyzerError):
        default_registry().create("нет")


def test_registry_checks_name_matches_analyzer_id() -> None:
    registry = AnalyzerRegistry()
    registry.register("length", MislabeledAnalyzer)
    with pytest.raises(AnalysisFailure):
        registry.create("length")


def test_registry_creates_new_instance_each_time() -> None:
    registry = default_registry()
    assert registry.create("length") is not registry.create("length")


def test_registries_are_independent() -> None:
    a, b = default_registry(), default_registry()
    a.register("declaration", DeclarationAnalyzer)
    assert "declaration" in a.names() and "declaration" not in b.names()


def make_service(
    submission: Submission, *extra: tuple[str, Callable[[], Analyzer]]
) -> tuple[AnalysisService, InMemorySubmissionRepository]:
    repo = InMemorySubmissionRepository()
    repo.add(submission)
    registry = default_registry()
    for name, factory in extra:
        registry.register(name, factory)
    return AnalysisService(repo, registry), repo


def test_service_runs_registered_analyzers(submission: Submission, context: AnalysisContext) -> None:
    service, _ = make_service(submission)
    for name in ("length", "template"):
        assert service.run("sub-001", name, context).analyzer_id == name


def test_service_requires_accepted_submission(context: AnalysisContext) -> None:
    service = AnalysisService(InMemorySubmissionRepository(), default_registry())
    with pytest.raises(AnalysisFailure):
        service.run("sub-001", "length", context)


def test_service_requires_matching_assignment_context(submission: Submission) -> None:
    service, _ = make_service(submission)
    with pytest.raises(AnalysisFailure):
        service.run("sub-001", "length", AnalysisContext(Assignment("assignment-02", "x")))


def test_defective_report_stops_and_submission_stays_intact(
    submission: Submission, context: AnalysisContext
) -> None:
    service, repo = make_service(submission, ("broken", BrokenAnalyzer))
    with pytest.raises(InvalidReportError):
        service.run("sub-001", "broken", context)
    assert repo.get("sub-001") == submission


def test_crashing_analyzer_is_wrapped_with_cause(
    submission: Submission, context: AnalysisContext
) -> None:
    service, repo = make_service(submission, ("crash", CrashingAnalyzer))
    with pytest.raises(AnalyzerCrashedError) as caught:
        service.run("sub-001", "crash", context)
    assert isinstance(caught.value.__cause__, ZeroDivisionError)
    assert caught.value.code == "analyzer_crashed"
    assert repo.get("sub-001") == submission
    # сервис остаётся рабочим после отказа плагина
    assert service.run("sub-001", "length", context).analyzer_id == "length"


def test_third_analyzer_plugs_in_without_changing_service(
    submission: Submission, context: AnalysisContext
) -> None:
    service, _ = make_service(submission)
    with pytest.raises(UnknownAnalyzerError):
        service.run("sub-001", "declaration", context)
    service.registry.register("declaration", DeclarationAnalyzer)  # только регистрация
    assert service.run("sub-001", "declaration", context).analyzer_id == "declaration"


def test_service_has_no_class_specific_branching() -> None:
    import inspect

    import school_intake.analysis_service as module

    source = inspect.getsource(module)
    for name in ("LengthAnalyzer", "TemplateAnalyzer", "DeclarationAnalyzer"):
        assert name not in source


def test_late_binding_fixed_when_registering_in_loop() -> None:
    registry = AnalyzerRegistry()
    for name, cls in (("length", LengthAnalyzer), ("template", TemplateAnalyzer)):
        registry.register(name, lambda cls=cls: cls())  # значение фиксируется аргументом
    assert [registry.create(n).analyzer_id for n in ("length", "template")] == ["length", "template"]
