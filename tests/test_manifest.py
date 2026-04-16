"""Unit tests for raiflow/manifest.py — load_manifest.

Requirements: 1.1, 1.2, 1.3, 1.4
"""

import warnings
from pathlib import Path

import pytest
import yaml

from raiflow.manifest import (
    DataGovernance,
    Logging,
    ModelMetadata,
    Oversight,
    RaiFlowManifest,
    RiskManagement,
    Robustness,
    load_manifest,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_MANIFEST = {
    "system_name": "Test RAG System",
    "risk_level": "high",
    "eu_ai_act_articles": ["Article 9", "Article 13"],
    "model_metadata": {
        "name": "my-model-v1",
        "version": "1.0.0",
        "disclosure_flag": True,
    },
    "logging": {"middleware_active": True},
}


def _write_yaml(tmp_path: Path, data: dict, filename: str = "raiflow.yaml") -> Path:
    p = tmp_path / filename
    with open(p, "w") as f:
        yaml.safe_dump(data, f)
    return p


# ---------------------------------------------------------------------------
# Requirement 1.2 — missing file raises FileNotFoundError with descriptive message
# ---------------------------------------------------------------------------


def test_missing_file_raises_file_not_found(tmp_path: Path) -> None:
    """load_manifest raises FileNotFoundError when the file does not exist."""
    missing = str(tmp_path / "nonexistent.yaml")
    with pytest.raises(FileNotFoundError) as exc_info:
        load_manifest(missing)
    msg = str(exc_info.value)
    assert "nonexistent.yaml" in msg, "Error message should include the missing path"
    assert "raiflow.yaml.example" in msg, "Error message should hint at the example file"


# ---------------------------------------------------------------------------
# Requirement 1.3 — unrecognised field emits warning and parses successfully
# ---------------------------------------------------------------------------


def test_unrecognised_field_emits_warning(tmp_path: Path) -> None:
    """load_manifest emits a warning for unknown top-level keys but still parses."""
    data = {**VALID_MANIFEST, "unknown_field": "some_value"}
    path = _write_yaml(tmp_path, data)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        manifest = load_manifest(str(path))

    warning_messages = [str(w.message) for w in caught]
    assert any("unknown_field" in m for m in warning_messages), (
        "Expected a warning about 'unknown_field'"
    )
    assert manifest.system_name == "Test RAG System"


def test_unrecognised_field_does_not_raise(tmp_path: Path) -> None:
    """load_manifest does not raise when an unrecognised field is present."""
    data = {**VALID_MANIFEST, "extra_key": 42}
    path = _write_yaml(tmp_path, data)
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        manifest = load_manifest(str(path))
    assert manifest is not None


# ---------------------------------------------------------------------------
# Requirement 1.1 / 1.4 — all required fields parse correctly
# ---------------------------------------------------------------------------


def test_valid_manifest_parses_all_required_fields(tmp_path: Path) -> None:
    """load_manifest correctly parses all required fields from a valid YAML."""
    path = _write_yaml(tmp_path, VALID_MANIFEST)
    manifest = load_manifest(str(path))

    assert manifest.system_name == "Test RAG System"
    assert manifest.risk_level == "high"
    assert manifest.eu_ai_act_articles == ["Article 9", "Article 13"]
    assert manifest.model_metadata.name == "my-model-v1"
    assert manifest.model_metadata.version == "1.0.0"
    assert manifest.model_metadata.disclosure_flag is True
    assert manifest.logging.middleware_active is True


def test_valid_manifest_optional_fields_have_defaults(tmp_path: Path) -> None:
    """Optional fields default correctly when absent from the YAML."""
    path = _write_yaml(tmp_path, VALID_MANIFEST)
    manifest = load_manifest(str(path))

    assert manifest.risk_management.assessment_path is None
    assert manifest.oversight.override_endpoints == []
    assert manifest.data_governance.dataset_path is None
    assert manifest.data_governance.protected_attributes == []
    assert manifest.robustness.toxicity_threshold == pytest.approx(0.7)
    assert manifest.banned_models == []


def test_full_manifest_with_all_optional_fields(tmp_path: Path) -> None:
    """load_manifest parses a fully-populated manifest including all optional fields."""
    data = {
        **VALID_MANIFEST,
        "risk_management": {"assessment_path": "docs/risk.md"},
        "oversight": {"override_endpoints": ["/api/override", "/api/halt"]},
        "data_governance": {
            "dataset_path": "data/train.csv",
            "format": "csv",
            "protected_attributes": ["gender", "ethnicity"],
        },
        "robustness": {
            "red_team_prompts_path": "tests/prompts.txt",
            "toxicity_threshold": 0.5,
        },
        "banned_models": ["social-scoring-model"],
    }
    path = _write_yaml(tmp_path, data)
    manifest = load_manifest(str(path))

    assert manifest.risk_management.assessment_path == "docs/risk.md"
    assert manifest.oversight.override_endpoints == ["/api/override", "/api/halt"]
    assert manifest.data_governance.dataset_path == "data/train.csv"
    assert manifest.data_governance.format == "csv"
    assert manifest.data_governance.protected_attributes == ["gender", "ethnicity"]
    assert manifest.robustness.red_team_prompts_path == "tests/prompts.txt"
    assert manifest.robustness.toxicity_threshold == pytest.approx(0.5)
    assert manifest.banned_models == ["social-scoring-model"]


def test_disclosure_flag_false_parses(tmp_path: Path) -> None:
    """disclosure_flag=False is a valid value and parses correctly."""
    data = {
        **VALID_MANIFEST,
        "model_metadata": {**VALID_MANIFEST["model_metadata"], "disclosure_flag": False},
    }
    path = _write_yaml(tmp_path, data)
    manifest = load_manifest(str(path))
    assert manifest.model_metadata.disclosure_flag is False


def test_model_version_defaults_to_empty_string(tmp_path: Path) -> None:
    """model_metadata.version defaults to empty string when omitted."""
    data = {
        **VALID_MANIFEST,
        "model_metadata": {"name": "my-model", "disclosure_flag": True},
    }
    path = _write_yaml(tmp_path, data)
    manifest = load_manifest(str(path))
    assert manifest.model_metadata.version == ""
