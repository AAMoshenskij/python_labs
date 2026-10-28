"""Стабильный отпечаток: SHA-256 от канонического JSON.

Встроенный ``hash()`` для строк меняется между процессами, поэтому для
идентификатора содержимого не подходит.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict

from .models import Submission


def canonical_json(value: object) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def stable_hash(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def submission_hash(value: Submission) -> str:
    """Хешируется вся сдача, включая идентификаторы и декларацию."""
    return stable_hash(asdict(value))
