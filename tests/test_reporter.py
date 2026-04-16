"""Unit tests for raiflow/reporter.py — build_report and write_report.

Requirements: 9.1, 9.2, 9.4
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from raiflow.gate import CheckResult
from raiflow.manifest import (
    DataGovernance,
    Logging,
    ModelMetadata,
    Oversight,
    RaiFlowManifest,
    RiskManagement,
    Robustness,
)
from raiflow.reporter import SCHEMA_VERSION, build_report, write_report


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_manifest(**overrides) -> RaiFlowManifest:
    defaults = dict(
        system_name="Test System",
        risk_level="high",
        eu_ai_act_articles=["Article 13"],
        model_metadata=ModelMetadata(name="safe-model", version="1.0", disclosure_flag=True),
        risk_management=RiskManagement(assessment_path=None),
        oversight=Oversight(override_endpoints=[]),
        logging=Logging(middleware_active=True),
        data_governance=DataGovernance(),
        robustness=Robustness(),
        banned_models=[],
    )
    defaults.update(overrides)
    return RaiFlowManifest(**defaults)


def _pass_check(**overrides) -> CheckResult:
    defaults = dict(
        article_id="Article 13",
        rule_id="ART13-1",
        check_name="Transparency by Design",
        status="pass",
        score=1.0,
        threshold=1.0,
    )
    defaults.update(overrides)
    return CheckResult(**defaults)


# ---------------------------------------------------------------------------
# build_report — required fields
# ---------------------------------------------------------------------------

class TestBuildReportFields:
    def test_all_required_top_level_fields_present(self):
        manifest = _make_manifest()
        checks = [_pass_check()]
        report = build_report("ci", manifest, checks, git_sha="abc1234")

        required = {
            "schema_version", "generated_at", "git_sha",
            "stage", "system_name", "overall_status", "checks",
        }
        assert required.issubset(report.keys())

    def test_schema_version_is_1_0(self):
        report = build_report("ci", _make_manifest(), [_pass_check()], git_sha="abc")
        assert report["schema_version"] == SCHEMA_VERSION
        assert report["schema_version"] == "1.0"

    def test_stage_matches_input(self):
        for stage in ("pre-commit", "ci", "pre-deploy", "post-deploy"):
            report = build_report(stage, _make_manifest(), [], git_sha="abc")
            assert report["stage"] == stage

    def test_system_name_matches_manifest(self):
        manifest = _make_manifest(system_name="My RAG System")
        report = build_report("ci", manifest, [], git_sha="abc")
        assert report["system_name"] == "My RAG System"

    def test_git_sha_uses_provided_value(self):
        report = build_report("ci", _make_manifest(), [], git_sha="deadbeef")
        assert report["git_sha"] == "deadbeef"

    def test_git_sha_falls_back_to_get_git_sha_when_none(self):
        with patch("raiflow.reporter._get_git_sha", return_value="fallback123"):
            report = build_report("ci", _make_manifest(), [], git_sha=None)
        assert report["git_sha"] == "fallback123"

    def test_generated_at_is_iso8601_string(self):
        from datetime import datetime, timezone
        report = build_report("ci", _make_manifest(), [], git_sha="abc")
        # Should parse without error
        dt = datetime.fromisoformat(report["generated_at"])
        assert dt.tzinfo is not None  # must be timezone-aware

    def test_checks_array_contains_all_check_fields(self):
        check = _pass_check(
            article_id="Article 13",
            rule_id="ART13-1",
            check_name="Transparency by Design",
            status="pass",
            score=1.0,
            threshold=1.0,
            remediation_hint="",
        )
        report = build_report("ci", _make_manifest(), [check], git_sha="abc")
        assert len(report["checks"]) == 1
        entry = report["checks"][0]
        for field in ("article_id", "rule_id", "check_name", "status", "score", "threshold", "remediation_hint"):
            assert field in entry, f"Missing field: {field}"


# ---------------------------------------------------------------------------
# build_report — overall_status logic
# ---------------------------------------------------------------------------

class TestBuildReportOverallStatus:
    def test_overall_status_fail_when_any_check_fails(self):
        checks = [
            _pass_check(status="pass"),
            _pass_check(status="fail", rule_id="ART9-1"),
        ]
        report = build_report("ci", _make_manifest(), checks, git_sha="abc")
        assert report["overall_status"] == "fail"

    def test_overall_status_pass_when_all_checks_pass(self):
        checks = [_pass_check(status="pass"), _pass_check(status="pass", rule_id="ART9-1")]
        report = build_report("ci", _make_manifest(), checks, git_sha="abc")
        assert report["overall_status"] == "pass"

    def test_overall_status_pass_when_all_checks_skipped(self):
        checks = [
            _pass_check(status="skipped"),
            _pass_check(status="skipped", rule_id="ART10-3"),
        ]
        report = build_report("ci", _make_manifest(), checks, git_sha="abc")
        assert report["overall_status"] == "pass"

    def test_overall_status_fail_when_mix_of_pass_skip_and_fail(self):
        checks = [
            _pass_check(status="pass"),
            _pass_check(status="skipped", rule_id="ART10-3"),
            _pass_check(status="fail", rule_id="ART9-1"),
        ]
        report = build_report("ci", _make_manifest(), checks, git_sha="abc")
        assert report["overall_status"] == "fail"

    def test_overall_status_pass_when_checks_empty(self):
        report = build_report("ci", _make_manifest(), [], git_sha="abc")
        assert report["overall_status"] == "pass"


# ---------------------------------------------------------------------------
# write_report — file I/O and directory creation
# ---------------------------------------------------------------------------

class TestWriteReport:
    def test_write_report_creates_valid_json(self, tmp_path):
        report = build_report("ci", _make_manifest(), [_pass_check()], git_sha="abc")
        output = tmp_path / "report.json"
        write_report(report, str(output))
        with open(output) as f:
            loaded = json.load(f)
        assert loaded["schema_version"] == "1.0"
        assert loaded["overall_status"] == "pass"

    def test_write_report_creates_parent_directories(self, tmp_path):
        nested_path = tmp_path / "nested" / "dir" / "report.json"
        report = build_report("ci", _make_manifest(), [], git_sha="abc")
        write_report(report, str(nested_path))
        assert nested_path.exists()
        with open(nested_path) as f:
            loaded = json.load(f)
        assert "schema_version" in loaded

    def test_write_report_produces_indented_json(self, tmp_path):
        report = {"schema_version": "1.0", "checks": []}
        output = tmp_path / "report.json"
        write_report(report, str(output))
        content = output.read_text()
        # Indented JSON has newlines
        assert "\n" in content

    def test_write_report_round_trip_identical(self, tmp_path):
        report = build_report("ci", _make_manifest(), [_pass_check()], git_sha="abc")
        output = tmp_path / "report.json"
        write_report(report, str(output))
        with open(output) as f:
            loaded = json.load(f)
        re_serialised = json.dumps(loaded, indent=2, sort_keys=True)
        assert output.read_text() == re_serialised
