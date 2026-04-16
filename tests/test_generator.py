"""Unit tests for raiflow/generator.py — TestGenerator.

Requirements: 4.2, 4.6, 4.7
"""

import tempfile
from pathlib import Path

import yaml

from raiflow.generator import TestGenerator

_POLICY_PATH = "policies/eu_ai_act.yaml"


def _count_articles(policy_path: str) -> int:
    """Return the number of regulatory_sections in the policy YAML."""
    with open(policy_path) as f:
        policy = yaml.safe_load(f)
    return len(policy.get("regulatory_sections", []))


# ---------------------------------------------------------------------------
# 4.2 — One file per article
# ---------------------------------------------------------------------------


def test_one_file_per_article():
    """One test_article_*.py file is produced per article in the policy YAML.

    Requirements: 4.2
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = TestGenerator(_POLICY_PATH)
        gen.generate(tmpdir)

        article_files = list(Path(tmpdir).glob("test_article_*.py"))
        expected = _count_articles(_POLICY_PATH)
        assert len(article_files) == expected, (
            f"Expected {expected} article test files, got {len(article_files)}: "
            f"{[f.name for f in article_files]}"
        )


# ---------------------------------------------------------------------------
# 4.7 — Rule ID comment embedded in each generated file
# ---------------------------------------------------------------------------


def test_rule_id_comment_in_generated_files():
    """Each generated article file contains the rule ID as a comment (e.g. # ART9-1).

    Requirements: 4.7
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = TestGenerator(_POLICY_PATH)
        gen.generate(tmpdir)

        with open(_POLICY_PATH) as f:
            policy = yaml.safe_load(f)

        for section in policy.get("regulatory_sections", []):
            slug = gen._article_slug(section)
            test_file = Path(tmpdir) / f"test_{slug}.py"
            assert test_file.exists(), f"Expected file {test_file.name} not found"

            content = test_file.read_text(encoding="utf-8")
            for rule in section.get("rules", []):
                rid = rule["rule_id"]
                assert f"# {rid}:" in content, (
                    f"Rule ID comment '# {rid}:' not found in {test_file.name}"
                )


# ---------------------------------------------------------------------------
# 4.6 — Re-running overwrites without error
# ---------------------------------------------------------------------------


def test_rerun_overwrites_without_error():
    """Calling generate() twice overwrites existing files without raising an exception.

    Requirements: 4.6
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = TestGenerator(_POLICY_PATH)
        # First run
        gen.generate(tmpdir)
        files_first = {f.name: f.read_text(encoding="utf-8") for f in Path(tmpdir).glob("*.py")}

        # Second run — must not raise
        gen.generate(tmpdir)
        files_second = {f.name: f.read_text(encoding="utf-8") for f in Path(tmpdir).glob("*.py")}

        assert files_first == files_second, (
            "Re-running generate() produced different file contents"
        )


# ---------------------------------------------------------------------------
# 4.3 — test_logging_exists.py is generated
# ---------------------------------------------------------------------------


def test_logging_exists_file_generated():
    """test_logging_exists.py is produced by the generator.

    Requirements: 4.3
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = TestGenerator(_POLICY_PATH)
        gen.generate(tmpdir)

        logging_file = Path(tmpdir) / "test_logging_exists.py"
        assert logging_file.exists(), "test_logging_exists.py was not generated"

        content = logging_file.read_text(encoding="utf-8")
        assert "middleware_active" in content
        assert "ART12-1" in content


# ---------------------------------------------------------------------------
# 4.4 — test_bias_metrics.py is generated
# ---------------------------------------------------------------------------


def test_bias_metrics_file_generated():
    """test_bias_metrics.py is produced by the generator.

    Requirements: 4.4
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = TestGenerator(_POLICY_PATH)
        gen.generate(tmpdir)

        bias_file = Path(tmpdir) / "test_bias_metrics.py"
        assert bias_file.exists(), "test_bias_metrics.py was not generated"

        content = bias_file.read_text(encoding="utf-8")
        assert "ART10-3" in content
        assert "bias_detection_check" in content
