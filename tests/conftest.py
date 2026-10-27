from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from school_intake.analysis_service import AnalysisService
from school_intake.analyzers import AnalysisContext, default_registry
from school_intake.models import Assignment, Submission
from school_intake.repository import InMemorySubmissionRepository
from school_intake.service import SubmissionService
from school_intake.validation import parse_submission

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

RAW_EXAMPLE: dict[str, Any] = {
    "schema_version": 1,
    "submission_id": "sub-001",
    "student_id": "student-001",
    "assignment_id": "assignment-01",
    "submitted_at": "2026-09-01T10:01:00+03:00",
    "text": "Учебное решение с пояснением алгоритма.",
    "code": (
        "from typing import Iterable\n\n"
        "def solve(values: Iterable[int]) -> int:\n"
        "    return sum(x * x for x in values if x >= 0)\n"
    ),
    "template_id": "template-01",
    "ai_declaration": {
        "used": False, "tool": None, "purpose": None, "verified_by_student": True,
    },
}

ASSIGNMENT = Assignment(
    "assignment-01", "from typing import Iterable\n", ("Наличие функции solve",)
)


def changed(**updates: object) -> dict[str, Any]:
    result = copy.deepcopy(RAW_EXAMPLE)
    result.update(updates)
    return result


def write_jsonl(path: Path, lines: list[str]) -> Path:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def dumps(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


@pytest.fixture
def raw_submission() -> dict[str, Any]:
    return copy.deepcopy(RAW_EXAMPLE)


@pytest.fixture
def submission(raw_submission: dict[str, Any]) -> Submission:
    return parse_submission(raw_submission)


@pytest.fixture
def repository() -> InMemorySubmissionRepository:
    return InMemorySubmissionRepository()


@pytest.fixture
def service(repository: InMemorySubmissionRepository) -> SubmissionService:
    return SubmissionService(repository)


@pytest.fixture
def context() -> AnalysisContext:
    return AnalysisContext(ASSIGNMENT)


@pytest.fixture
def analysis_service(repository: InMemorySubmissionRepository) -> AnalysisService:
    return AnalysisService(repository, default_registry())
