"""Unit tests for semantic LLM evaluator integration in raiflow/gate.py.

Requirements: 1.4, 1.5, 2.1, 2.7, 3.6, 5.2, 5.3, 5.4, 5.6, 7.3, 10.4
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from raiflow.gate import CheckResult, CheckRunner, LlmConfig, load_llm_config
from raiflow.manifest import (
    DataGovernance,
    Logging,
    ModelMetadata,
    Oversight,
    RaiFlowManifest,
    RiskManagement,
    Robustness,
    TechnicalDocumentation,
)
from raiflow.reporter import build_report


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_manifest(**overrides) -> RaiFlowManifest:
    """Build a minimal compliant manifest with optional field overrides."""
    defaults = dict(
        system_name="Test System",
        risk_level="high",
        eu_ai_act_articles=["Article 9", "Article 11", "Article 13"],
        model_metadata=ModelMetadata(name="safe-model-v1", version="1.0", disclosure_flag=True),
        risk_management=RiskManagement(assessment_path=None),
        oversight=Oversight(override_endpoints=[]),
        logging=Logging(middleware_active=True),
        data_governance=DataGovernance(dataset_path=None),
        robustness=Robustness(red_team_prompts_path=None, toxicity_threshold=0.7),
        banned_models=[],
        technical_documentation=TechnicalDocumentation(path=None),
    )
    defaults.update(overrides)
    return RaiFlowManifest(**defaults)


def _make_runner(manifest: RaiFlowManifest, **kwargs) -> CheckRunner:
    """Create a CheckRunner with a patched ComplianceEngine to avoid file I/O."""
    with patch("raiflow.gate.ComplianceEngine"):
        return CheckRunner(manifest, **kwargs)


# ---------------------------------------------------------------------------
# Requirement 1.4 — LlmConfig loading
# ---------------------------------------------------------------------------

class TestLoadLlmConfig:
    def test_load_llm_config_valid(self, tmp_path):
        """Config file with mode=local loads correctly into LlmConfig."""
        config_file = tmp_path / "llm_config.json"
        config_file.write_text(json.dumps({
            "mode": "local",
            "model": "llama3.2:3b",
            "env_var": None,
        }))
        cfg = load_llm_config(path=config_file)
        assert isinstance(cfg, LlmConfig)
        assert cfg.mode == "local"
        assert cfg.model == "llama3.2:3b"
        assert cfg.env_var is None

    def test_load_llm_config_api_missing_env_var(self, tmp_path, monkeypatch):
        """Raises ValueError with descriptive message naming the missing variable."""
        config_file = tmp_path / "llm_config.json"
        config_file.write_text(json.dumps({
            "mode": "api",
            "model": "gemini-1.5-flash",
            "env_var": "GEMMA_API_KEY",
        }))
        # Ensure the env var is not set
        monkeypatch.delenv("GEMMA_API_KEY", raising=False)

        with pytest.raises(ValueError) as exc_info:
            load_llm_config(path=config_file)

        assert "GEMMA_API_KEY" in str(exc_info.value)

    def test_load_llm_config_missing_file(self, tmp_path):
        """Raises FileNotFoundError when config file does not exist."""
        missing_path = tmp_path / "nonexistent_config.json"
        with pytest.raises(FileNotFoundError):
            load_llm_config(path=missing_path)


# ---------------------------------------------------------------------------
# Requirement 2.1 — Static transparency check
# ---------------------------------------------------------------------------

class TestCheckTransparencyStatic:
    def test_check_transparency_static_pass(self):
        """disclosure_flag=True → status='pass', enable_llm_checks=False."""
        m = _make_manifest(
            model_metadata=ModelMetadata(name="m", version="1.0", disclosure_flag=True)
        )
        runner = _make_runner(m, enable_llm_checks=False)
        result = runner._check_transparency()
        assert result.status == "pass"
        assert result.score == 1.0

    def test_check_transparency_static_fail(self):
        """disclosure_flag=False → status='fail', enable_llm_checks=False."""
        m = _make_manifest(
            model_metadata=ModelMetadata(name="m", version="1.0", disclosure_flag=False)
        )
        runner = _make_runner(m, enable_llm_checks=False)
        result = runner._check_transparency()
        assert result.status == "fail"
        assert result.score == 0.0


# ---------------------------------------------------------------------------
# Requirement 2.7 — LLM unavailable fallback for transparency
# ---------------------------------------------------------------------------

class TestCheckTransparencySemanticFallback:
    def test_check_transparency_semantic_llm_unavailable(self, tmp_path):
        """LLM exception → static fallback with '(LLM unavailable — static fallback used)' in hint."""
        # Create a real disclosure text file
        disclosure_file = tmp_path / "disclosure.txt"
        disclosure_file.write_text("This system is powered by AI.")

        m = _make_manifest(
            model_metadata=ModelMetadata(name="m", version="1.0", disclosure_flag=True)
        )
        runner = _make_runner(m, enable_llm_checks=True)

        # Monkeypatch disclosure_text_path onto model_metadata so the semantic path is entered
        runner.manifest.model_metadata.__dict__["disclosure_text_path"] = str(disclosure_file)

        with patch.object(runner, "_load_evaluator", side_effect=RuntimeError("LLM down")):
            result = runner._check_transparency()

        assert "(LLM unavailable — static fallback used)" in result.remediation_hint


# ---------------------------------------------------------------------------
# Requirement 3.6 — Risk management missing file, no LLM call
# ---------------------------------------------------------------------------

class TestCheckRiskManagementMissingFile:
    def test_check_risk_management_missing_file_no_llm_call(self, tmp_path):
        """enable_llm_checks=True, file missing → skip_reason='missing_evidence', LLM not called."""
        missing_path = tmp_path / "nonexistent_risk.md"
        m = _make_manifest(
            risk_management=RiskManagement(assessment_path=str(missing_path))
        )
        runner = _make_runner(m, enable_llm_checks=True)

        mock_load_evaluator = MagicMock()
        with patch.object(runner, "_load_evaluator", mock_load_evaluator):
            result = runner._check_risk_management()

        assert result.skip_reason == "missing_evidence"
        mock_load_evaluator.assert_not_called()


# ---------------------------------------------------------------------------
# Requirement 5.2, 5.3, 5.4 — Technical documentation checks
# ---------------------------------------------------------------------------

class TestCheckTechnicalDocumentation:
    def test_check_technical_documentation_no_path(self):
        """Manifest without technical_documentation.path → fail, skip_reason='missing_evidence'."""
        m = _make_manifest(technical_documentation=TechnicalDocumentation(path=None))
        runner = _make_runner(m, enable_llm_checks=False)
        result = runner._check_technical_documentation()
        assert result.status == "fail"
        assert result.skip_reason == "missing_evidence"

    def test_check_technical_documentation_path_missing_file(self, tmp_path):
        """Path declared but file absent → fail, skip_reason='missing_evidence'."""
        missing_file = tmp_path / "tech_doc.md"
        m = _make_manifest(
            technical_documentation=TechnicalDocumentation(path=str(missing_file))
        )
        runner = _make_runner(m, enable_llm_checks=False)
        result = runner._check_technical_documentation()
        assert result.status == "fail"
        assert result.skip_reason == "missing_evidence"

    def test_check_technical_documentation_pass(self, tmp_path):
        """File exists, enable_llm_checks=False → pass, score=1.0."""
        doc_file = tmp_path / "tech_doc.md"
        doc_file.write_text("# Technical Documentation\nThis is the system description.")
        m = _make_manifest(
            technical_documentation=TechnicalDocumentation(path=str(doc_file))
        )
        runner = _make_runner(m, enable_llm_checks=False)
        result = runner._check_technical_documentation()
        assert result.status == "pass"
        assert result.score == 1.0


# ---------------------------------------------------------------------------
# Requirement 7.3 — Threshold resolution for unknown rule
# ---------------------------------------------------------------------------

class TestResolveThreshold:
    def test_resolve_threshold_missing_rule(self):
        """Unknown rule ID → returns 0.85, emits warnings.warn."""
        m = _make_manifest()
        runner = _make_runner(m)
        # Ensure the policy has no rules (empty policy)
        runner.engine.policy = {"regulatory_sections": []}

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            threshold = runner._resolve_threshold("UNKNOWN-RULE-999")

        assert threshold == 0.85
        assert len(caught) == 1
        assert "UNKNOWN-RULE-999" in str(caught[0].message)


# ---------------------------------------------------------------------------
# Requirement 5.6 — Article 11 check result fields
# ---------------------------------------------------------------------------

class TestArticle11CheckResultFields:
    def test_article_11_check_result_fields(self, tmp_path):
        """Result has article_id='Article 11', rule_id='ART11-1', check_name='Technical Documentation'."""
        doc_file = tmp_path / "tech_doc.md"
        doc_file.write_text("Technical documentation content.")
        m = _make_manifest(
            technical_documentation=TechnicalDocumentation(path=str(doc_file))
        )
        runner = _make_runner(m, enable_llm_checks=False)
        result = runner._check_technical_documentation()
        assert result.article_id == "Article 11"
        assert result.rule_id == "ART11-1"
        assert result.check_name == "Technical Documentation"


# ---------------------------------------------------------------------------
# Requirement 5.5 — TechnicalDocumentation manifest default
# ---------------------------------------------------------------------------

class TestTechnicalDocumentationManifestDefault:
    def test_technical_documentation_manifest_default(self):
        """Manifest YAML without technical_documentation block parses with path=None."""
        minimal_yaml = {
            "system_name": "My System",
            "risk_level": "high",
            "model_metadata": {
                "name": "my-model",
                "version": "1.0",
                "disclosure_flag": True,
            },
            "logging": {"middleware_active": True},
        }
        manifest = RaiFlowManifest(**minimal_yaml)
        assert manifest.technical_documentation.path is None


# ---------------------------------------------------------------------------
# Requirement 10.4 — evaluation_mode field in report
# ---------------------------------------------------------------------------

class TestEvaluationModeFieldInReport:
    def _make_check(self) -> CheckResult:
        return CheckResult(
            article_id="Article 13",
            rule_id="ART13-1",
            check_name="Transparency by Design",
            status="pass",
            score=1.0,
            threshold=1.0,
        )

    def test_evaluation_mode_semantic_when_llm_enabled(self):
        """build_report(..., enable_llm_checks=True) → 'evaluation_mode': 'semantic'."""
        manifest = _make_manifest()
        report = build_report("ci", manifest, [self._make_check()], git_sha="abc", enable_llm_checks=True)
        assert report["evaluation_mode"] == "semantic"

    def test_evaluation_mode_static_when_llm_disabled(self):
        """build_report(..., enable_llm_checks=False) → 'evaluation_mode': 'static'."""
        manifest = _make_manifest()
        report = build_report("ci", manifest, [self._make_check()], git_sha="abc", enable_llm_checks=False)
        assert report["evaluation_mode"] == "static"
