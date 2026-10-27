"""Entry points: внешние анализаторы без изменения основного приложения."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from school_intake.analysis_service import AnalysisService
from school_intake.analyzers import AnalysisContext, default_registry
from school_intake.errors import AnalysisFailure, PluginLoadError
from school_intake.models import Submission
from school_intake.plugins import ENTRY_POINT_GROUP, discover, load_plugins
from school_intake.repository import InMemorySubmissionRepository

PLUGIN_SOURCE = textwrap.dedent(
    '''
    from school_intake.analyzers import AnalysisContext, AnalysisReport, Finding, make_report
    from school_intake.models import Submission


    class CustomAnalyzer:
        analyzer_id = "custom"
        analyzer_version = "0.1"

        def analyze(self, submission: Submission, context: AnalysisContext) -> AnalysisReport:
            finding = Finding("rubric_feedback", None, (), "Внешний анализатор отработал.")
            return make_report(submission, context, self.analyzer_id, self.analyzer_version, (finding,))
    '''
)


def install_fake_distribution(root: Path, entry_name: str, target: str) -> None:
    """Создаёт на диске минимальный установленный пакет (dist-info) с entry point."""
    (root / "fake_plugin.py").write_text(PLUGIN_SOURCE, encoding="utf-8")
    info = root / "fake_plugin-1.0.dist-info"
    info.mkdir()
    (info / "METADATA").write_text("Metadata-Version: 2.1\nName: fake-plugin\nVersion: 1.0\n")
    (info / "entry_points.txt").write_text(f"[{ENTRY_POINT_GROUP}]\n{entry_name} = {target}\n")


def test_installed_plugin_is_discovered_and_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, submission: Submission, context: AnalysisContext
) -> None:
    install_fake_distribution(tmp_path, "custom", "fake_plugin:CustomAnalyzer")
    monkeypatch.syspath_prepend(str(tmp_path))
    assert "custom" in {entry.name for entry in discover()}

    registry = default_registry()
    assert load_plugins(registry) == ["custom"]
    repo = InMemorySubmissionRepository()
    repo.add(submission)
    report = AnalysisService(repo, registry).run("sub-001", "custom", context)
    assert report.analyzer_id == "custom"  # центральный сервис не менялся


def test_directory_on_disk_is_not_a_registration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "fake_plugin.py").write_text(PLUGIN_SOURCE, encoding="utf-8")  # без dist-info
    monkeypatch.syspath_prepend(str(tmp_path))
    assert "custom" not in {entry.name for entry in discover()}


class FakeEntry:
    def __init__(self, name: str, target: object = None, error: Exception | None = None) -> None:
        self.name, self._target, self._error = name, target, error

    def load(self) -> object:
        if self._error is not None:
            raise self._error
        return self._target


def test_duplicate_plugin_name_is_rejected() -> None:
    registry = default_registry()
    with pytest.raises(AnalysisFailure):
        load_plugins(registry, [FakeEntry("length", lambda: None)])


def test_import_error_becomes_plugin_load_error() -> None:
    with pytest.raises(PluginLoadError) as caught:
        load_plugins(default_registry(), [FakeEntry("broken", error=ImportError("нет модуля"))])
    assert isinstance(caught.value.__cause__, ImportError)


def test_non_callable_target_is_rejected() -> None:
    with pytest.raises(PluginLoadError):
        load_plugins(default_registry(), [FakeEntry("odd", target=42)])


def test_entry_name_must_match_analyzer_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_fake_distribution(tmp_path, "wrong-name", "fake_plugin:CustomAnalyzer")
    monkeypatch.syspath_prepend(str(tmp_path))
    registry = default_registry()
    load_plugins(registry)
    with pytest.raises(AnalysisFailure):
        registry.create("wrong-name")
