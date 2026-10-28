from __future__ import annotations

import copy
import dataclasses
from typing import Any

import pytest

from conftest import RAW_EXAMPLE, changed, dumps
from school_intake.errors import ConflictError, FormatError, SchemaError
from school_intake.hashing import canonical_json, stable_hash, submission_hash
from school_intake.models import Submission
from school_intake.repository import InMemorySubmissionRepository
from school_intake.service import SubmissionService
from school_intake.validation import parse_submission


def test_valid_submission_is_accepted(
    service: SubmissionService, repository: InMemorySubmissionRepository, raw_submission: dict[str, Any]
) -> None:
    result = service.accept(raw_submission)
    assert result.status == "accepted"
    assert result.submission_id == "sub-001"
    assert len(repository) == 1
    assert repository.get("sub-001") == parse_submission(RAW_EXAMPLE)


def test_duplicate_returns_existing_and_does_not_grow(
    service: SubmissionService, repository: InMemorySubmissionRepository
) -> None:
    first = service.accept(RAW_EXAMPLE)
    second = service.accept(copy.deepcopy(RAW_EXAMPLE))
    assert second.status == "duplicate"
    assert second.submission is first.submission  # возвращена уже принятая сдача
    assert second.content_hash == first.content_hash
    assert len(repository) == 1


def test_conflict_does_not_overwrite_original(
    service: SubmissionService, repository: InMemorySubmissionRepository
) -> None:
    service.accept(RAW_EXAMPLE)
    previous = repository.get("sub-001")
    with pytest.raises(ConflictError) as caught:
        service.accept(changed(code="print('другая версия')"))
    assert (caught.value.code, caught.value.field) == ("conflict", "submission_id")
    assert repository.get("sub-001") is previous
    assert len(repository) == 1


def test_invalid_schema_leaves_repository_untouched(
    service: SubmissionService, repository: InMemorySubmissionRepository
) -> None:
    with pytest.raises(SchemaError):
        service.accept(changed(student_id=""))
    assert len(repository) == 0


def test_new_version_with_new_id_keeps_both(
    service: SubmissionService, repository: InMemorySubmissionRepository
) -> None:
    service.accept(RAW_EXAMPLE)
    result = service.accept(changed(submission_id="sub-001-v2", code="print('v2')"))
    assert result.status == "accepted"
    assert len(repository) == 2
    assert repository.get("sub-001") != repository.get("sub-001-v2")


def test_accept_line_works_without_cli(service: SubmissionService) -> None:
    assert service.accept_line(dumps(RAW_EXAMPLE)).status == "accepted"
    with pytest.raises(FormatError):
        service.accept_line("{")


def test_repository_add_refuses_overwrite(
    repository: InMemorySubmissionRepository, submission: Submission
) -> None:
    repository.add(submission)
    with pytest.raises(ConflictError):
        repository.add(dataclasses.replace(submission, text="другой"))


def test_submission_is_frozen(submission: Submission) -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        submission.student_id = "other"  # type: ignore[misc]


# --- хеш ----------------------------------------------------------------------


def test_hash_is_stable_and_independent_of_key_order(submission: Submission) -> None:
    reordered = dict(reversed(list(RAW_EXAMPLE.items())))
    assert submission_hash(parse_submission(reordered)) == submission_hash(submission)
    assert len(submission_hash(submission)) == 64


def test_hash_changes_with_content(submission: Submission) -> None:
    base = submission_hash(submission)
    assert submission_hash(dataclasses.replace(submission, code=submission.code + "\n")) != base
    assert submission_hash(dataclasses.replace(submission, student_id="other")) != base


def test_same_code_of_different_students_gives_different_hash() -> None:
    a = parse_submission(changed(submission_id="a", student_id="s-a"))
    b = parse_submission(changed(submission_id="b", student_id="s-b"))
    assert a.code == b.code and submission_hash(a) != submission_hash(b)


def test_same_instant_in_other_representation_gives_different_hash() -> None:
    # Следствие контракта: submitted_at хранится как исходная строка.
    a = parse_submission(changed(submitted_at="2026-09-01T10:01:00+03:00"))
    b = parse_submission(changed(submitted_at="2026-09-01T07:01:00+00:00"))
    assert submission_hash(a) != submission_hash(b)


def test_canonical_json_rejects_nan_and_keeps_unicode() -> None:
    assert canonical_json({"б": 1, "а": 2}) == '{"а":2,"б":1}'
    with pytest.raises(ValueError):
        stable_hash({"x": float("nan")})
