"""Unit tests for raiflow/gate.py — CheckRunner and CheckResult."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from raiflow.gate import CheckResult, CheckRunner
from raiflow.manifest import (
    DataGovernance,
    Logging,
    ModelMetadata,
    Oversight,
    RaiFlowManifest,
    RiskManagement,
    Robustness,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_manifest(**overrides) -> RaiFlowManifest:
    """Build a minimal compliant manifest, with optional field overrides."""
    defaults = dict(
        system_name="Test System",
        risk_level="high",
        eu_ai_act_articles=["Article 9", "Article 12", "Article 13", "Article 14"],
        model_metadata=ModelMetadata(name="safe-model-v1", version="1.0", disclosure_flag=True),
        risk_management=RiskManagement(assessment_path=None),
        oversight=Oversight(override_endpoints=[]),
        logging=Logging(middleware_active=True),
        data_governance=DataGovernance(dataset_path=None),
        robustness=Robustness(red_team_prompts_path=None, toxicity_threshold=0.7),
        banned_models=[],
    )
    defaults.update(overrides)
    return RaiFlowManifest(**defaults)


def _make_runner(manifest: RaiFlowManifest, **kwargs) -> CheckRunner:
    """Create a CheckRunner with a patched ComplianceEngine to avoid file I/O."""
    with patch("raiflow.gate.ComplianceEngine"):
        return CheckRunner(manifest, **kwargs)


# ---------------------------------------------------------------------------
# CheckResult dataclass
# ---------------------------------------------------------------------------

class TestCheckResult:
    def test_defaults(self):
        r = CheckResult(
            article_id="Article 13",
            rule_id="ART13-1",
            check_name="Transparency",
            status="pass",
            score=1.0,
            threshold=1.0,
        )
        assert r.remediation_hint == ""
        assert r.skip_reason == ""

    def test_all_fields(self):
        r = CheckResult(
            article_id="Article 9",
            rule_id="ART9-1",
            check_name="Risk Mgmt",
            status="fail",
            score=0.0,
            threshold=1.0,
            remediation_hint="Fix it",
            skip_reason="missing_evidence",
        )
        assert r.status == "fail"
        assert r.skip_reason == "missing_evidence"


# ---------------------------------------------------------------------------
# _check_transparency (Article 13)
# ---------------------------------------------------------------------------

class TestCheckTransparency:
    def test_pass_when_disclosure_flag_true(self):
        m = _make_manifest()
        runner = _make_runner(m)
        result = runner._check_transparency()
        assert result.status == "pass"
        assert result.score == 1.0
        assert result.rule_id == "ART13-1"

    def test_fail_when_disclosure_flag_false(self):
        m = _make_manifest(
            model_metadata=ModelMetadata(name="m", disclosure_flag=False)
        )
        runner = _make_runner(m)
        result = runner._check_transparency()
        assert result.status == "fail"
        assert result.score == 0.0
        assert "disclosure_flag" in result.remediation_hint
        assert "Article 13" in result.remediation_hint

    def test_article_id_correct(self):
        m = _make_manifest()
        runner = _make_runner(m)
        result = runner._check_transparency()
        assert result.article_id == "Article 13"


# ---------------------------------------------------------------------------
# _check_risk_management (Article 9)
# ---------------------------------------------------------------------------

class TestCheckRiskManagement:
    def test_pass_when_file_exists(self, tmp_path):
        doc = tmp_path / "risk.md"
        doc.write_text("risk assessment")
        m = _make_manifest(risk_management=RiskManagement(assessment_path=str(doc)))
        runner = _make_runner(m)
        result = runner._check_risk_management()
        assert result.status == "pass"
        assert result.score == 1.0

    def test_fail_when_path_is_none(self):
        m = _make_manifest(risk_management=RiskManagement(assessment_path=None))
        runner = _make_runner(m)
        result = runner._check_risk_management()
        assert result.status == "fail"
        assert result.skip_reason == "missing_evidence"

    def test_fail_when_file_not_found(self):
        m = _make_manifest(
            risk_management=RiskManagement(assessment_path="/nonexistent/path/risk.md")
        )
        runner = _make_runner(m)
        result = runner._check_risk_management()
        assert result.status == "fail"
        assert result.skip_reason == "missing_evidence"
        assert "risk_management.assessment_path" in result.remediation_hint

    def test_no_exception_on_missing_file(self):
        """Missing file must record fail, not raise."""
        m = _make_manifest(
            risk_management=RiskManagement(assessment_path="/does/not/exist.md")
        )
        runner = _make_runner(m)
        # Should not raise
        result = runner._check_risk_management()
        assert result.status == "fail"


# ---------------------------------------------------------------------------
# _check_human_oversight (Article 14)
# ---------------------------------------------------------------------------

class TestCheckHumanOversight:
    def test_fail_when_no_target_files(self):
        m = _make_manifest(oversight=Oversight(override_endpoints=["/api/halt"]))
        runner = _make_runner(m)
        result = runner._check_human_oversight()
        assert result.status == "fail"
        assert result.skip_reason == "missing_evidence"
        assert "--target" in result.remediation_hint

    def test_pass_when_all_endpoints_found(self, tmp_path):
        src = tmp_path / "app.py"
        src.write_text('app.route("/api/override")\napp.route("/api/halt")\n')
        m = _make_manifest(
            oversight=Oversight(override_endpoints=["/api/override", "/api/halt"])
        )
        runner = _make_runner(m, target_files=[str(src)])
        result = runner._check_human_oversight()
        assert result.status == "pass"
        assert result.score == 1.0

    def test_fail_when_endpoint_missing_from_files(self, tmp_path):
        src = tmp_path / "app.py"
        src.write_text('app.route("/api/override")\n')
        m = _make_manifest(
            oversight=Oversight(override_endpoints=["/api/override", "/api/halt"])
        )
        runner = _make_runner(m, target_files=[str(src)])
        result = runner._check_human_oversight()
        assert result.status == "fail"
        assert "/api/halt" in result.remediation_hint

    def test_pass_when_no_endpoints_declared(self, tmp_path):
        src = tmp_path / "app.py"
        src.write_text("# empty\n")
        m = _make_manifest(oversight=Oversight(override_endpoints=[]))
        runner = _make_runner(m, target_files=[str(src)])
        result = runner._check_human_oversight()
        assert result.status == "pass"

    def test_no_exception_when_target_file_missing(self):
        """Missing target file must not raise — endpoint simply won't be found."""
        m = _make_manifest(
            oversight=Oversight(override_endpoints=["/api/halt"])
        )
        runner = _make_runner(m, target_files=["/nonexistent/file.py"])
        result = runner._check_human_oversight()
        assert result.status == "fail"
        assert result.skip_reason == ""  # not missing_evidence, just not found


# ---------------------------------------------------------------------------
# _check_logging (Article 12)
# ---------------------------------------------------------------------------

class TestCheckLogging:
    def test_pass_when_middleware_active(self):
        m = _make_manifest(logging=Logging(middleware_active=True))
        runner = _make_runner(m)
        result = runner._check_logging()
        assert result.status == "pass"
        assert result.score == 1.0
        assert result.rule_id == "ART12-1"

    def test_fail_when_middleware_inactive(self):
        m = _make_manifest(logging=Logging(middleware_active=False))
        runner = _make_runner(m)
        result = runner._check_logging()
        assert result.status == "fail"
        assert result.score == 0.0
        assert "middleware_active" in result.remediation_hint
        assert "Article 12" in result.remediation_hint


# ---------------------------------------------------------------------------
# _check_banned_models
# ---------------------------------------------------------------------------

class TestCheckBannedModels:
    def test_pass_when_model_not_banned(self):
        m = _make_manifest(
            model_metadata=ModelMetadata(name="safe-model", disclosure_flag=True),
            banned_models=["bad-model", "evil-model"],
        )
        runner = _make_runner(m)
        result = runner._check_banned_models()
        assert result.status == "pass"
        assert result.rule_id == "BAN-1"

    def test_fail_when_model_is_banned(self):
        m = _make_manifest(
            model_metadata=ModelMetadata(name="bad-model", disclosure_flag=True),
            banned_models=["bad-model", "evil-model"],
        )
        runner = _make_runner(m)
        result = runner._check_banned_models()
        assert result.status == "fail"
        assert "bad-model" in result.remediation_hint

    def test_pass_when_banned_list_empty(self):
        m = _make_manifest(
            model_metadata=ModelMetadata(name="any-model", disclosure_flag=True),
            banned_models=[],
        )
        runner = _make_runner(m)
        result = runner._check_banned_models()
        assert result.status == "pass"


# ---------------------------------------------------------------------------
# _check_bias_detection (Article 10)
# ---------------------------------------------------------------------------

class TestCheckBiasDetection:
    def test_skipped_when_no_dataset_path(self):
        m = _make_manifest(data_governance=DataGovernance(dataset_path=None))
        runner = _make_runner(m)
        result = runner._check_bias_detection()
        assert result.status == "skipped"
        assert result.skip_reason == "no_dataset_declared"
        assert result.rule_id == "ART10-3"

    def test_pass_when_bias_score_above_threshold(self):
        m = _make_manifest(
            data_governance=DataGovernance(
                dataset_path="data/train.csv",
                protected_attributes=["gender"],
            )
        )
        runner = _make_runner(m)
        mock_evaluators = MagicMock()
        mock_evaluators.bias_detection_check.return_value = 0.95
        with patch("raiflow.gate.EUAIActEvaluators", return_value=mock_evaluators):
            result = runner._check_bias_detection()
        assert result.status == "pass"
        assert result.score == 0.95

    def test_fail_when_bias_score_below_threshold(self):
        m = _make_manifest(
            data_governance=DataGovernance(dataset_path="data/train.csv")
        )
        runner = _make_runner(m)
        mock_evaluators = MagicMock()
        mock_evaluators.bias_detection_check.return_value = 0.50
        with patch("raiflow.gate.EUAIActEvaluators", return_value=mock_evaluators):
            result = runner._check_bias_detection()
        assert result.status == "fail"
        assert result.score == 0.50

    def test_threshold_override_applied(self):
        m = _make_manifest(
            data_governance=DataGovernance(dataset_path="data/train.csv")
        )
        runner = _make_runner(m, threshold_override=0.5)
        mock_evaluators = MagicMock()
        mock_evaluators.bias_detection_check.return_value = 0.6
        with patch("raiflow.gate.EUAIActEvaluators", return_value=mock_evaluators):
            result = runner._check_bias_detection()
        assert result.status == "pass"
        assert result.threshold == 0.5

    def test_no_exception_when_evaluator_raises(self):
        m = _make_manifest(
            data_governance=DataGovernance(dataset_path="data/train.csv")
        )
        runner = _make_runner(m)
        mock_evaluators = MagicMock()
        mock_evaluators.bias_detection_check.side_effect = RuntimeError("LLM down")
        with patch("raiflow.gate.EUAIActEvaluators", return_value=mock_evaluators):
            result = runner._check_bias_detection()
        assert result.status == "fail"
        assert "LLM down" in result.remediation_hint


# ---------------------------------------------------------------------------
# _check_robustness (Article 10)
# ---------------------------------------------------------------------------

class TestCheckRobustness:
    def test_skipped_when_no_prompts_path(self):
        m = _make_manifest(robustness=Robustness(red_team_prompts_path=None))
        runner = _make_runner(m)
        result = runner._check_robustness()
        assert result.status == "skipped"
        assert result.rule_id == "ART10-4"

    def test_pass_when_all_prompts_safe(self, tmp_path):
        prompts_file = tmp_path / "prompts.txt"
        prompts_file.write_text("Hello world\nWhat is the weather?\n")
        m = _make_manifest(
            robustness=Robustness(
                red_team_prompts_path=str(prompts_file),
                toxicity_threshold=0.7,
            )
        )
        runner = _make_runner(m)
        # check_toxicity returns 1.0 = safe → toxicity = 0.0, below threshold 0.7
        with patch("raiflow.gate.check_toxicity", return_value=1.0):
            result = runner._check_robustness()
        assert result.status == "pass"
        assert "2" in result.remediation_hint  # 2 prompts tested

    def test_fail_when_toxic_prompt_found(self, tmp_path):
        prompts_file = tmp_path / "prompts.txt"
        prompts_file.write_text("safe prompt\ntoxic prompt\n")
        m = _make_manifest(
            robustness=Robustness(
                red_team_prompts_path=str(prompts_file),
                toxicity_threshold=0.7,
            )
        )
        runner = _make_runner(m)
        # First call safe (1.0), second call toxic (0.0 → toxicity 1.0 > 0.7)
        with patch("raiflow.gate.check_toxicity", side_effect=[1.0, 0.0]):
            result = runner._check_robustness()
        assert result.status == "fail"
        assert "1" in result.remediation_hint  # 1 failure

    def test_fail_when_prompts_file_missing(self):
        m = _make_manifest(
            robustness=Robustness(red_team_prompts_path="/nonexistent/prompts.txt")
        )
        runner = _make_runner(m)
        result = runner._check_robustness()
        assert result.status == "fail"
        assert result.skip_reason == "missing_evidence"

    def test_remediation_hint_contains_stats(self, tmp_path):
        prompts_file = tmp_path / "prompts.txt"
        prompts_file.write_text("p1\np2\np3\n")
        m = _make_manifest(
            robustness=Robustness(
                red_team_prompts_path=str(prompts_file),
                toxicity_threshold=0.7,
            )
        )
        runner = _make_runner(m)
        with patch("raiflow.gate.check_toxicity", return_value=1.0):
            result = runner._check_robustness()
        assert "3" in result.remediation_hint  # 3 prompts tested
        assert "max toxicity" in result.remediation_hint.lower()


# ---------------------------------------------------------------------------
# run() — stage dispatch
# ---------------------------------------------------------------------------

class TestRunStageDispatch:
    def _runner_with_mocked_checks(self, manifest: RaiFlowManifest) -> CheckRunner:
        runner = _make_runner(manifest)
        # Replace all check methods with mocks returning a pass result
        for method in [
            "_check_transparency",
            "_check_risk_management",
            "_check_human_oversight",
            "_check_logging",
            "_check_banned_models",
            "_check_bias_detection",
            "_check_robustness",
            "_check_technical_documentation",
        ]:
            mock_result = CheckResult(
                article_id="X", rule_id="X-1", check_name=method,
                status="pass", score=1.0, threshold=1.0,
            )
            setattr(runner, method, MagicMock(return_value=mock_result))
        return runner

    def test_pre_commit_only_runs_banned_model_scan(self):
        m = _make_manifest()
        runner = self._runner_with_mocked_checks(m)
        results = runner.run("pre-commit")
        runner._check_banned_models.assert_called_once()
        runner._check_transparency.assert_not_called()
        runner._check_risk_management.assert_not_called()
        runner._check_human_oversight.assert_not_called()
        runner._check_logging.assert_not_called()
        runner._check_bias_detection.assert_not_called()
        runner._check_robustness.assert_not_called()
        assert len(results) == 1

    def test_ci_runs_all_checks_including_bias_and_robustness(self):
        m = _make_manifest()
        runner = self._runner_with_mocked_checks(m)
        results = runner.run("ci")
        runner._check_banned_models.assert_called_once()
        runner._check_transparency.assert_called_once()
        runner._check_risk_management.assert_called_once()
        runner._check_human_oversight.assert_called_once()
        runner._check_logging.assert_called_once()
        runner._check_bias_detection.assert_called_once()
        runner._check_robustness.assert_called_once()
        assert len(results) == 8

    def test_pre_deploy_runs_all_checks_including_bias_and_robustness(self):
        m = _make_manifest()
        runner = self._runner_with_mocked_checks(m)
        results = runner.run("pre-deploy")
        runner._check_bias_detection.assert_called_once()
        runner._check_robustness.assert_called_once()
        assert len(results) == 8

    def test_post_deploy_skips_bias_and_robustness(self):
        m = _make_manifest()
        runner = self._runner_with_mocked_checks(m)
        results = runner.run("post-deploy")
        runner._check_bias_detection.assert_not_called()
        runner._check_robustness.assert_not_called()
        runner._check_transparency.assert_called_once()
        runner._check_logging.assert_called_once()
        assert len(results) == 5

    def test_run_returns_list_of_check_results(self):
        m = _make_manifest()
        runner = self._runner_with_mocked_checks(m)
        results = runner.run("ci")
        assert all(isinstance(r, CheckResult) for r in results)
