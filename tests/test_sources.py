"""Один набор контрактных тестов для обоих источников."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from conftest import changed, dumps, write_jsonl
from school_intake.errors import FormatError
from school_intake.sources import InMemorySource, JSONLSource, SubmissionSource

VALUES: list[dict[str, Any]] = [changed(submission_id=f"sub-{n}") for n in (1, 2, 3)]

Factory = Callable[[Path], SubmissionSource]


def make_jsonl(tmp_path: Path) -> SubmissionSource:
    return JSONLSource(write_jsonl(tmp_path / "s.jsonl", [dumps(v) for v in VALUES]))


def make_memory(tmp_path: Path) -> SubmissionSource:
    return InMemorySource(VALUES)


both = pytest.mark.parametrize("factory", [make_jsonl, make_memory], ids=["jsonl", "memory"])


@both
def test_yields_records_in_order_with_line_numbers(factory: Factory, tmp_path: Path) -> None:
    with factory(tmp_path).open() as records:
        loaded = list(records)
    assert [r.line_no for r in loaded] == [1, 2, 3]
    assert [r.raw for r in loaded] == VALUES
    assert all(r.error is None for r in loaded)


@both
def test_source_does_not_validate_schema(factory: Factory, tmp_path: Path) -> None:
    # Схему проверяет parser: источник отдаёт любой корректный JSON-объект.
    source = InMemorySource([{"anything": 1}])
    with source.open() as records:
        assert next(records).raw == {"anything": 1}


@both
def test_can_be_read_twice(factory: Factory, tmp_path: Path) -> None:
    source = factory(tmp_path)
    for _ in range(2):
        with source.open() as records:
            assert len(list(records)) == 3


def test_jsonl_closed_after_full_read(tmp_path: Path) -> None:
    source = make_jsonl(tmp_path)
    with source.open() as records:
        list(records)
    assert source.last_closed is True  # type: ignore[attr-defined]


def test_jsonl_closed_on_early_stop(tmp_path: Path) -> None:
    source = JSONLSource(write_jsonl(tmp_path / "s.jsonl", [dumps(v) for v in VALUES]))
    with source.open() as records:
        for record in records:
            if record.line_no == 1:
                break
    assert source.last_closed is True


def test_jsonl_closed_when_consumer_raises(tmp_path: Path) -> None:
    source = JSONLSource(write_jsonl(tmp_path / "s.jsonl", [dumps(v) for v in VALUES]))
    with pytest.raises(RuntimeError, match="сбой"), source.open() as records:
        next(records)
        raise RuntimeError("сбой потребителя")  # исключение не подавляется
    assert source.last_closed is True


def test_jsonl_file_handle_is_really_closed_after_exit(tmp_path: Path) -> None:
    source = JSONLSource(write_jsonl(tmp_path / "s.jsonl", [dumps(v) for v in VALUES]))
    with source.open() as records:
        next(records)
    with pytest.raises(ValueError):  # итератор после выхода из контекста непригоден
        next(records)


def test_jsonl_file_can_be_deleted_after_read(tmp_path: Path) -> None:
    # На Windows открытый файл удалить нельзя — косвенная проверка освобождения.
    path = write_jsonl(tmp_path / "s.jsonl", [dumps(VALUES[0])])
    with JSONLSource(path).open() as records:
        list(records)
    path.unlink()
    assert not path.exists()


def test_jsonl_reports_bad_lines_and_continues(tmp_path: Path) -> None:
    path = write_jsonl(tmp_path / "s.jsonl", [dumps(VALUES[0]), "{", "", dumps(VALUES[1])])
    with JSONLSource(path).open() as records:
        loaded = list(records)
    assert [r.line_no for r in loaded] == [1, 2, 3, 4]
    assert [r.error is not None for r in loaded] == [False, True, True, False]
    error = loaded[1].error
    assert isinstance(error, FormatError) and error.code == "invalid_json"
    assert loaded[2].error is not None  # пустая строка — invalid_json по политике источника


def test_missing_file_is_source_error_not_record_error(tmp_path: Path) -> None:
    source = JSONLSource(tmp_path / "нет.jsonl")
    with pytest.raises(FileNotFoundError), source.open():
        pass  # pragma: no cover
    assert source.last_closed is None


def test_memory_source_gives_copies(tmp_path: Path) -> None:
    source = InMemorySource(VALUES)
    with source.open() as records:
        first = next(records)
        assert isinstance(first.raw, dict)
        first.raw["code"] = "испорчено"
    with source.open() as records:
        assert next(records).raw == VALUES[0]
    assert VALUES[0]["code"] != "испорчено"


def test_memory_source_copies_input_collection() -> None:
    values = [changed(submission_id="x")]
    source = InMemorySource(values)
    values[0]["code"] = "испорчено после создания"
    with source.open() as records:
        raw = next(records).raw
    assert isinstance(raw, dict) and raw["code"] != "испорчено после создания"
