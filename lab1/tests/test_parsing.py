from __future__ import annotations

import copy
from dataclasses import asdict
from typing import Any

import pytest

from conftest import RAW_EXAMPLE, changed, dumps
from school_intake.errors import FormatError, SchemaError, UnsupportedVersionError
from school_intake.parser import decode_json, parse_line
from school_intake.validation import parse_submission


def test_valid_record_is_parsed_and_roundtrips(raw_submission: dict[str, Any]) -> None:
    value = parse_submission(raw_submission)
    assert asdict(value) == RAW_EXAMPLE  # исходное содержимое сохранено без изменений


def test_original_newlines_and_timestamp_are_preserved() -> None:
    raw = changed(code="a\r\n\n b\n", submitted_at="2026-09-01T07:01:00Z")
    value = parse_submission(raw)
    assert value.code == "a\r\n\n b\n"
    assert value.submitted_at == "2026-09-01T07:01:00Z"


def test_template_id_may_be_null() -> None:
    assert parse_submission(changed(template_id=None)).template_id is None


VALIDATION_CASES: list[tuple[dict[str, Any], str, str]] = [
    (changed(schema_version=True), "schema_error", "schema_version"),
    (changed(schema_version=2), "unsupported_version", "schema_version"),
    (changed(schema_version="1"), "schema_error", "schema_version"),
    (changed(code=123), "schema_error", "code"),
    (changed(text=None), "schema_error", "text"),
    (changed(submitted_at="2026-09-01T10:00:00"), "schema_error", "submitted_at"),
    (changed(submitted_at="вчера"), "schema_error", "submitted_at"),
    (changed(submitted_at=1756700000), "schema_error", "submitted_at"),
    (changed(student_id="  "), "schema_error", "student_id"),
    (changed(student_id=""), "schema_error", "student_id"),
    (changed(student_id=42), "schema_error", "student_id"),
    (changed(submission_id=None), "schema_error", "submission_id"),
    (changed(template_id=" "), "schema_error", "template_id"),
    (changed(template_id=5), "schema_error", "template_id"),
    (changed(unknown="value"), "schema_error", "unknown"),
    (changed(text=" ", code="\n"), "schema_error", "text/code"),
    (changed(ai_declaration={"used": True, "tool": None, "purpose": None,
                              "verified_by_student": False}), "schema_error", "ai_declaration"),
    (changed(ai_declaration={"used": True, "tool": "x", "purpose": " ",
                              "verified_by_student": False}), "schema_error",
     "ai_declaration.purpose"),
    (changed(ai_declaration={"used": "false", "tool": None, "purpose": None,
                              "verified_by_student": True}), "schema_error", "ai_declaration.used"),
    (changed(ai_declaration={"used": False, "tool": None, "purpose": None,
                              "verified_by_student": 1}), "schema_error",
     "ai_declaration.verified_by_student"),
    (changed(ai_declaration={"used": False, "tool": None, "purpose": None,
                              "verified_by_student": True, "extra": 1}), "schema_error",
     "ai_declaration.extra"),
    (changed(ai_declaration={"used": False, "tool": None, "verified_by_student": True}),
     "schema_error", "ai_declaration.purpose"),
    (changed(ai_declaration=[]), "schema_error", "ai_declaration"),
    (changed(ai_declaration=None), "schema_error", "ai_declaration"),
]


@pytest.mark.parametrize(("raw", "code", "field"), VALIDATION_CASES)
def test_schema_violations_are_explained_and_input_unchanged(
    raw: dict[str, Any], code: str, field: str
) -> None:
    before = copy.deepcopy(raw)
    with pytest.raises(SchemaError) as caught:
        parse_submission(raw)
    assert (caught.value.code, caught.value.field) == (code, field)
    assert caught.value.message
    assert raw == before  # вход не изменён и при ошибке


def test_unsupported_version_is_distinct_error_type() -> None:
    with pytest.raises(UnsupportedVersionError):
        parse_submission(changed(schema_version=2))


def test_missing_field_is_reported() -> None:
    raw = changed()
    del raw["student_id"]
    with pytest.raises(SchemaError) as caught:
        parse_submission(raw)
    assert caught.value.field == "student_id"


def test_typo_in_field_name_reports_unknown_field() -> None:
    raw = changed()
    raw["studnet_id"] = raw.pop("student_id")
    with pytest.raises(SchemaError) as caught:
        parse_submission(raw)
    assert caught.value.field == "studnet_id"


@pytest.mark.parametrize("raw", [[], "строка", 42, None])
def test_non_object_is_schema_error(raw: object) -> None:
    with pytest.raises(SchemaError):
        parse_submission(raw)


def test_success_does_not_mutate_input(raw_submission: dict[str, Any]) -> None:
    before = copy.deepcopy(raw_submission)
    parse_submission(raw_submission)
    assert raw_submission == before


@pytest.mark.parametrize(
    ("line", "field"),
    [
        ("{broken", "json"),
        ("", "json"),
        ('{"student_id":"a", "student_id":"b"}', "student_id"),
        ('{"score": NaN}', "json"),
        ('{"score": Infinity}', "json"),
        # короткий id: иначе имя теста длиннее лимита переменной окружения Windows
        pytest.param("[" * 100000, "json", id="deep-nesting"),
    ],
)
def test_invalid_json_is_format_error(line: str, field: str) -> None:
    with pytest.raises(FormatError) as caught:
        decode_json(line)
    assert caught.value.code == "invalid_json"
    assert caught.value.field == field


def test_valid_json_with_bad_schema_is_not_format_error() -> None:
    with pytest.raises(SchemaError):
        parse_line(dumps(changed(student_id="")))
    assert parse_line(dumps(RAW_EXAMPLE)).submission_id == "sub-001"
