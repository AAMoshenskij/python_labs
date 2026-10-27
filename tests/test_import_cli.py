from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import DATA_DIR, RAW_EXAMPLE, changed, dumps, write_jsonl
from school_intake.cli import main
from school_intake.importer import import_source
from school_intake.repository import InMemorySubmissionRepository
from school_intake.service import SubmissionService
from school_intake.sources import InMemorySource, JSONLSource


def mixed_lines() -> list[str]:
    return [
        dumps(RAW_EXAMPLE),                                                  # 1 accepted
        "{broken",                                                           # 2 invalid_json
        dumps(RAW_EXAMPLE),                                                  # 3 duplicate
        dumps(changed(text="Другое содержимое с тем же ID")),                # 4 conflict
        dumps(changed(submission_id="bad-record", student_id="")),           # 5 schema_error
        dumps(changed(submission_id="sub-002")),                             # 6 accepted
    ]


def test_import_partial_success(tmp_path: Path) -> None:
    repo = InMemorySubmissionRepository()
    summary = import_source(
        JSONLSource(write_jsonl(tmp_path / "m.jsonl", mixed_lines())), SubmissionService(repo)
    )
    assert summary.accepted == ["sub-001", "sub-002"]
    assert summary.duplicate == ["sub-001"]
    assert {e["line_no"]: e["code"] for e in summary.errors} == {
        2: "invalid_json", 4: "conflict", 5: "schema_error",
    }
    assert len(repo) == 2  # корректные записи сохранены, сдача 1 не перезаписана
    assert repo.get("sub-001") is not None and repo.get("sub-001").text == RAW_EXAMPLE["text"]  # type: ignore[union-attr]


def test_import_from_memory_source() -> None:
    repo = InMemorySubmissionRepository()
    summary = import_source(InMemorySource([RAW_EXAMPLE, {"bad": 1}]), SubmissionService(repo))
    assert summary.accepted == ["sub-001"]
    assert summary.errors[0]["line_no"] == 2


def test_unexpected_defects_are_not_swallowed() -> None:
    class Boom:
        def accept(self, raw: object) -> object:
            raise ZeroDivisionError

    with pytest.raises(ZeroDivisionError):
        import_source(InMemorySource([RAW_EXAMPLE]), Boom())  # type: ignore[arg-type]


def test_cli_import_exit_code_and_single_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = write_jsonl(tmp_path / "m.jsonl", mixed_lines())
    assert main(["import", str(path)]) == 1  # ошибки отдельных строк
    out = capsys.readouterr()
    payload = json.loads(out.out)  # в stdout ровно один JSON
    assert payload["accepted"] == ["sub-001", "sub-002"]
    assert out.err == ""


def test_cli_import_success_is_zero(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = write_jsonl(tmp_path / "ok.jsonl", [dumps(RAW_EXAMPLE)])
    assert main(["import", str(path)]) == 0
    assert json.loads(capsys.readouterr().out)["errors"] == []


def test_cli_missing_file_is_exit_2_with_stderr(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["import", str(tmp_path / "нет.jsonl")]) == 2
    out = capsys.readouterr()
    assert out.out == ""
    assert json.loads(out.err)["code"] == "source_unavailable"


def test_cli_through_installed_entry_module(tmp_path: Path) -> None:
    path = write_jsonl(tmp_path / "ok.jsonl", [dumps(RAW_EXAMPLE)])
    proc = subprocess.run(
        [sys.executable, "-m", "school_intake.cli", "import", str(path)],
        capture_output=True, encoding="utf-8", check=True,
    )
    assert json.loads(proc.stdout)["accepted"] == ["sub-001"]


@pytest.mark.skipif(not (DATA_DIR / "submissions.jsonl").exists(), reason="нет data/")
def test_public_corpus_end_to_end(capsys: pytest.CaptureFixture[str]) -> None:
    code = main([
        "analyze", str(DATA_DIR / "submissions.jsonl"),
        "--assignments", str(DATA_DIR / "assignments.json"), "--no-plugins",
    ])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert len(payload["import"]["accepted"]) == 12 and not payload["import"]["errors"]
    assert len(payload["reports"]) == 24 and payload["failures"] == []


@pytest.mark.skipif(not (DATA_DIR / "invalid_submissions.jsonl").exists(), reason="нет data/")
def test_invalid_corpus_continues_after_each_bad_line(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["import", str(DATA_DIR / "invalid_submissions.jsonl")]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["accepted"] == ["sub-002"]  # единственная корректная строка принята
    assert len(payload["errors"]) == 12


def test_cli_analyze_reports_unknown_assignment(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = write_jsonl(tmp_path / "a.jsonl", [dumps(changed(assignment_id="other"))])
    assignments = tmp_path / "assignments.json"
    assignments.write_text(json.dumps([
        {"assignment_id": "assignment-01", "allowed_template": "x\n", "requirements": []}
    ]), encoding="utf-8")
    assert main(["analyze", str(path), "--assignments", str(assignments), "--no-plugins"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["failures"][0]["code"] == "unknown_assignment"


def test_cli_analyze_bad_assignments_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{не json", encoding="utf-8")
    path = write_jsonl(tmp_path / "a.jsonl", [dumps(RAW_EXAMPLE)])
    assert main(["analyze", str(path), "--assignments", str(bad)]) == 2
    assert json.loads(capsys.readouterr().err)["code"] == "assignments_unavailable"
