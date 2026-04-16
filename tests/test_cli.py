"""Unit tests for raiflow/cli.py — Click CLI using CliRunner.

Tests use unittest.mock.patch to isolate the CLI from real I/O.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from raiflow.cli import cli
from raiflow.gate import CheckResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pass_result() -> CheckResult:
    return CheckResult(
        article_id="Article 13",
        rule_id="ART13-1",
        check_name="Transparency by Design",
        status="pass",
        score=1.0,
        threshold=1.0,
    )


def _fail_result() -> CheckResult:
    return CheckResult(
        article_id="Article 9",
        rule_id="ART9-1",
        check_name="Risk Management Documentation",
        status="fail",
        score=0.0,
        threshold=1.0,
        remediation_hint="Create a risk assessment document.",
    )


def _mock_runner(results):
    """Return a mock CheckRunner class whose .run() returns *results*."""
    mock_instance = MagicMock()
    mock_instance.run.return_value = results
    mock_cls = MagicMock(return_value=mock_instance)
    return mock_cls


# ---------------------------------------------------------------------------
# Test: all checks pass → exit code 0
# ---------------------------------------------------------------------------

class TestCheckAllPass:
    def test_exit_code_zero_on_all_pass(self):
        """Requirement 2.4: exit 0 when all checks pass."""
        runner = CliRunner()
        mock_manifest = MagicMock()
        mock_runner_cls = _mock_runner([_pass_result()])

        with patch("raiflow.cli.load_manifest", return_value=mock_manifest), \
             patch("raiflow.cli.CheckRunner", mock_runner_cls), \
             patch("raiflow.cli.build_report", return_value={"overall_status": "pass"}), \
             patch("raiflow.cli.write_report"):
            result = runner.invoke(cli, ["check", "--stage", "ci"])

        assert result.exit_code == 0

    def test_success_message_printed_on_all_pass(self):
        runner = CliRunner()
        mock_manifest = MagicMock()
        mock_runner_cls = _mock_runner([_pass_result()])

        with patch("raiflow.cli.load_manifest", return_value=mock_manifest), \
             patch("raiflow.cli.CheckRunner", mock_runner_cls), \
             patch("raiflow.cli.build_report", return_value={}), \
             patch("raiflow.cli.write_report"):
            result = runner.invoke(cli, ["check", "--stage", "ci"])

        assert "All checks passed" in result.output
        assert "stage=ci" in result.output


# ---------------------------------------------------------------------------
# Test: one or more checks fail → exit code 1
# ---------------------------------------------------------------------------

class TestCheckFailure:
    def test_exit_code_one_on_failure(self):
        """Requirement 2.5: exit 1 when any check fails."""
        runner = CliRunner()
        mock_manifest = MagicMock()
        mock_runner_cls = _mock_runner([_fail_result()])

        with patch("raiflow.cli.load_manifest", return_value=mock_manifest), \
             patch("raiflow.cli.CheckRunner", mock_runner_cls), \
             patch("raiflow.cli.build_report", return_value={"overall_status": "fail"}), \
             patch("raiflow.cli.write_report"):
            result = runner.invoke(cli, ["check", "--stage", "ci"])

        assert result.exit_code == 1

    def test_failure_table_printed_on_failure(self):
        """Requirement 6.2: structured failure table includes all required fields."""
        runner = CliRunner()
        mock_manifest = MagicMock()
        fail = _fail_result()
        mock_runner_cls = _mock_runner([fail])

        with patch("raiflow.cli.load_manifest", return_value=mock_manifest), \
             patch("raiflow.cli.CheckRunner", mock_runner_cls), \
             patch("raiflow.cli.build_report", return_value={}), \
             patch("raiflow.cli.write_report"):
            result = runner.invoke(cli, ["check", "--stage", "pre-deploy"])

        output = result.output
        assert fail.article_id in output
        assert fail.rule_id in output
        assert fail.check_name in output
        assert f"{fail.score:.2f}" in output
        assert f"{fail.threshold:.2f}" in output
        assert fail.remediation_hint in output

    def test_failure_count_shown(self):
        runner = CliRunner()
        mock_manifest = MagicMock()
        mock_runner_cls = _mock_runner([_fail_result(), _fail_result()])

        with patch("raiflow.cli.load_manifest", return_value=mock_manifest), \
             patch("raiflow.cli.CheckRunner", mock_runner_cls), \
             patch("raiflow.cli.build_report", return_value={}), \
             patch("raiflow.cli.write_report"):
            result = runner.invoke(cli, ["check", "--stage", "ci"])

        assert "2 check(s) failed" in result.output


# ---------------------------------------------------------------------------
# Test: --dry-run always exits 0
# ---------------------------------------------------------------------------

class TestDryRun:
    def test_dry_run_exits_zero_even_when_checks_fail(self):
        """Requirement 6.4: --dry-run always exits 0."""
        runner = CliRunner()
        mock_manifest = MagicMock()
        mock_runner_cls = _mock_runner([_fail_result()])

        with patch("raiflow.cli.load_manifest", return_value=mock_manifest), \
             patch("raiflow.cli.CheckRunner", mock_runner_cls), \
             patch("raiflow.cli.build_report", return_value={}), \
             patch("raiflow.cli.write_report"):
            result = runner.invoke(cli, ["check", "--stage", "ci", "--dry-run"])

        assert result.exit_code == 0

    def test_dry_run_still_prints_failure_table(self):
        """--dry-run should still report failures, just not block."""
        runner = CliRunner()
        mock_manifest = MagicMock()
        fail = _fail_result()
        mock_runner_cls = _mock_runner([fail])

        with patch("raiflow.cli.load_manifest", return_value=mock_manifest), \
             patch("raiflow.cli.CheckRunner", mock_runner_cls), \
             patch("raiflow.cli.build_report", return_value={}), \
             patch("raiflow.cli.write_report"):
            result = runner.invoke(cli, ["check", "--stage", "ci", "--dry-run"])

        assert fail.rule_id in result.output

    def test_dry_run_exits_zero_on_all_pass(self):
        runner = CliRunner()
        mock_manifest = MagicMock()
        mock_runner_cls = _mock_runner([_pass_result()])

        with patch("raiflow.cli.load_manifest", return_value=mock_manifest), \
             patch("raiflow.cli.CheckRunner", mock_runner_cls), \
             patch("raiflow.cli.build_report", return_value={}), \
             patch("raiflow.cli.write_report"):
            result = runner.invoke(cli, ["check", "--stage", "ci", "--dry-run"])

        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Test: missing raiflow.yaml → non-zero exit with human-readable error
# ---------------------------------------------------------------------------

class TestMissingManifest:
    def test_missing_manifest_exits_nonzero(self):
        """Requirement 1.2: missing manifest exits non-zero."""
        runner = CliRunner()

        with patch(
            "raiflow.cli.load_manifest",
            side_effect=FileNotFoundError(
                "Compliance manifest not found: 'raiflow.yaml'\n"
                "Hint: cp raiflow.yaml.example raiflow.yaml"
            ),
        ):
            result = runner.invoke(cli, ["check", "--stage", "ci"])

        assert result.exit_code != 0

    def test_missing_manifest_prints_human_readable_error(self):
        """Requirement 1.2: error message must be human-readable."""
        runner = CliRunner()
        error_msg = (
            "Compliance manifest not found: 'raiflow.yaml'\n"
            "Hint: cp raiflow.yaml.example raiflow.yaml"
        )

        with patch("raiflow.cli.load_manifest", side_effect=FileNotFoundError(error_msg)):
            result = runner.invoke(cli, ["check", "--stage", "ci"])

        # Error is written to stderr; CliRunner mixes stdout+stderr by default
        assert "raiflow.yaml" in result.output or "raiflow.yaml" in (result.stderr if hasattr(result, "stderr") else "")

    def test_missing_manifest_error_contains_filename(self):
        runner = CliRunner()
        error_msg = "Compliance manifest not found: 'custom.yaml'\nHint: ..."

        with patch("raiflow.cli.load_manifest", side_effect=FileNotFoundError(error_msg)):
            result = runner.invoke(cli, ["check", "--stage", "ci", "--manifest", "custom.yaml"])

        assert result.exit_code != 0
        assert "custom.yaml" in result.output


# ---------------------------------------------------------------------------
# Test: --stage omitted → defaults to 'ci' with warning
# ---------------------------------------------------------------------------

class TestDefaultStage:
    def test_no_stage_defaults_to_ci(self):
        """Requirement 2.8: omitting --stage defaults to ci."""
        runner = CliRunner()
        mock_manifest = MagicMock()
        mock_runner_cls = _mock_runner([_pass_result()])

        with patch("raiflow.cli.load_manifest", return_value=mock_manifest), \
             patch("raiflow.cli.CheckRunner", mock_runner_cls), \
             patch("raiflow.cli.build_report", return_value={}), \
             patch("raiflow.cli.write_report"):
            result = runner.invoke(cli, ["check"])

        assert result.exit_code == 0
        # Warning is written to stderr; CliRunner mixes stderr into output by default
        assert "Warning" in result.output
        assert "ci" in result.output

    def test_no_stage_warning_recommends_explicit_stage(self):
        runner = CliRunner()
        mock_manifest = MagicMock()
        mock_runner_cls = _mock_runner([_pass_result()])

        with patch("raiflow.cli.load_manifest", return_value=mock_manifest), \
             patch("raiflow.cli.CheckRunner", mock_runner_cls), \
             patch("raiflow.cli.build_report", return_value={}), \
             patch("raiflow.cli.write_report"):
            result = runner.invoke(cli, ["check"])

        assert "--stage" in result.output


# ---------------------------------------------------------------------------
# Test: COMPLIANCE_NOTIFY_EMAIL env var → writes raiflow-notify.json
# ---------------------------------------------------------------------------

class TestNotifyEmail:
    def test_notify_json_written_when_env_set(self, tmp_path, monkeypatch):
        """Requirement 6.5: write raiflow-notify.json when env var is set."""
        monkeypatch.setenv("COMPLIANCE_NOTIFY_EMAIL", "ops@example.com")
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        mock_manifest = MagicMock()
        mock_runner_cls = _mock_runner([_fail_result()])

        with patch("raiflow.cli.load_manifest", return_value=mock_manifest), \
             patch("raiflow.cli.CheckRunner", mock_runner_cls), \
             patch("raiflow.cli.build_report", return_value={}), \
             patch("raiflow.cli.write_report"):
            result = runner.invoke(cli, ["check", "--stage", "pre-deploy"])

        notify_file = tmp_path / "raiflow-notify.json"
        assert notify_file.exists()
        import json
        payload = json.loads(notify_file.read_text())
        assert payload["recipient"] == "ops@example.com"
        assert "failures" in payload
        assert "timestamp" in payload

    def test_notify_json_not_written_when_env_unset(self, tmp_path, monkeypatch):
        monkeypatch.delenv("COMPLIANCE_NOTIFY_EMAIL", raising=False)
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        mock_manifest = MagicMock()
        mock_runner_cls = _mock_runner([_fail_result()])

        with patch("raiflow.cli.load_manifest", return_value=mock_manifest), \
             patch("raiflow.cli.CheckRunner", mock_runner_cls), \
             patch("raiflow.cli.build_report", return_value={}), \
             patch("raiflow.cli.write_report"):
            runner.invoke(cli, ["check", "--stage", "ci"])

        assert not (tmp_path / "raiflow-notify.json").exists()
