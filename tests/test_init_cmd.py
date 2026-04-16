"""Unit tests for raiflow init command (Task 6).

Tests cover scanner, scaffolder, and CLI integration.
"""
from __future__ import annotations

import importlib.resources
import io
import sys
from pathlib import Path
from unittest.mock import patch, mock_open

import pytest
from click.testing import CliRunner

from raiflow.cli import cli
from raiflow.scanner import (
    ALL_FRAMEWORKS,
    DetectionResult,
    scan_directory,
)
from raiflow.scaffolder import (
    SummaryResult,
    WriteResult,
    print_summary,
    render_manifest,
    write_manifest,
    write_workflow,
)


# ── Scanner tests ─────────────────────────────────────────────────────────────

def test_scan_empty_directory(tmp_path):
    """Empty directory returns DetectionResult with no frameworks and minimal risk."""
    result = scan_directory(tmp_path)
    assert result.frameworks == []
    assert result.risk_level == "minimal"


def test_scan_detects_each_known_framework(tmp_path):
    """Each framework in ALL_FRAMEWORKS is detected when imported in a .py file."""
    for i, framework in enumerate(ALL_FRAMEWORKS):
        fw_dir = tmp_path / f"fw_{i}"
        fw_dir.mkdir(parents=True, exist_ok=True)
        (fw_dir / "test.py").write_text(f"import {framework}\n", encoding="utf-8")

    result = scan_directory(tmp_path)
    for framework in ALL_FRAMEWORKS:
        assert framework in result.frameworks, f"{framework} not detected"


def test_scan_excludes_venv(tmp_path):
    """Framework imports inside .venv/ are not included in detection results."""
    venv_lib = tmp_path / ".venv" / "lib"
    venv_lib.mkdir(parents=True)
    (venv_lib / "site.py").write_text("import langchain\n", encoding="utf-8")

    result = scan_directory(tmp_path)
    assert "langchain" not in result.frameworks


def test_scan_skips_unreadable_file(tmp_path):
    """PermissionError on a file adds it to skipped_files without raising."""
    target = tmp_path / "secret.py"
    target.write_text("import langchain\n", encoding="utf-8")

    original_read_text = Path.read_text

    def patched_read_text(self, *args, **kwargs):
        if self == target:
            raise PermissionError("Permission denied")
        return original_read_text(self, *args, **kwargs)

    with patch.object(Path, "read_text", patched_read_text):
        result = scan_directory(tmp_path)

    assert target in result.skipped_files
    assert "langchain" not in result.frameworks


# ── Manifest rendering tests ──────────────────────────────────────────────────

def test_render_manifest_high_risk(tmp_path):
    """High-risk detection renders YAML with all 6 EU AI Act articles."""
    detection = DetectionResult(frameworks=["langchain"], risk_level="high")
    rendered = render_manifest(detection, system_name="myproject")

    for article in ["Article 9", "Article 10", "Article 11", "Article 12", "Article 13", "Article 14"]:
        assert article in rendered, f"{article} missing from high-risk manifest"


def test_render_manifest_limited_risk(tmp_path):
    """Limited-risk detection renders YAML with only Article 13 in eu_ai_act_articles."""
    detection = DetectionResult(frameworks=["transformers"], risk_level="limited")
    rendered = render_manifest(detection, system_name="myproject")

    # Extract only the eu_ai_act_articles block to avoid matching comments elsewhere
    assert "Article 13" in rendered
    # Articles 9-12 and 14 must not appear as list items (they may appear in comments)
    import re
    articles_block_match = re.search(
        r"eu_ai_act_articles:\s*((?:\s*-\s*\"Article \d+\"\s*)+)", rendered
    )
    assert articles_block_match, "eu_ai_act_articles block not found"
    articles_block = articles_block_match.group(1)
    for article in ["Article 9", "Article 10", "Article 11", "Article 12", "Article 14"]:
        assert article not in articles_block, f"{article} should not be in limited-risk articles list"


def test_render_manifest_no_frameworks(tmp_path):
    """No-framework detection uses dir basename as system_name and 'my-ai-model' as model name."""
    detection = DetectionResult(frameworks=[], risk_level="minimal")
    system_name = tmp_path.name
    rendered = render_manifest(detection, system_name=system_name)

    assert system_name in rendered
    assert "my-ai-model" in rendered


# ── File writer tests ─────────────────────────────────────────────────────────

def test_write_manifest_no_overwrite(tmp_path):
    """Existing raiflow.yaml is not overwritten when force=False."""
    manifest_path = tmp_path / "raiflow.yaml"
    manifest_path.write_text("original content", encoding="utf-8")

    result = write_manifest("new content", tmp_path, force=False)

    assert manifest_path.read_text(encoding="utf-8") == "original content"
    assert result.action == "skipped"


def test_write_manifest_force_overwrites(tmp_path):
    """Existing raiflow.yaml is overwritten when force=True."""
    manifest_path = tmp_path / "raiflow.yaml"
    manifest_path.write_text("original content", encoding="utf-8")

    result = write_manifest("new content", tmp_path, force=True)

    assert manifest_path.read_text(encoding="utf-8") == "new content"
    assert result.action == "overwritten"


def test_write_workflow_creates_dirs(tmp_path):
    """write_workflow creates .github/workflows/ and writes rai-compliance.yml."""
    result = write_workflow(tmp_path, force=False)

    workflows_dir = tmp_path / ".github" / "workflows"
    assert workflows_dir.is_dir()
    assert (workflows_dir / "rai-compliance.yml").exists()


def test_write_workflow_content_matches_package_data(tmp_path):
    """Written workflow file content matches the embedded package data template."""
    write_workflow(tmp_path, force=False)

    written = (tmp_path / ".github" / "workflows" / "rai-compliance.yml").read_text(encoding="utf-8")
    expected = (
        importlib.resources.files("raiflow.data")
        .joinpath("rai-compliance.yml")
        .read_text(encoding="utf-8")
    )
    assert written == expected


# ── Summary output tests ──────────────────────────────────────────────────────

def test_summary_contains_next_command(tmp_path, capsys):
    """print_summary outputs 'raiflow check --stage ci' to stdout."""
    detection = DetectionResult(frameworks=["openai"], risk_level="high")
    wr = WriteResult(path=tmp_path / "raiflow.yaml", action="written")
    summary = SummaryResult(detection=detection, write_results=[wr])

    print_summary(summary)

    captured = capsys.readouterr()
    assert "raiflow check --stage ci" in captured.out


def test_summary_skipped_file_notice(tmp_path, capsys):
    """print_summary includes the skipped file path in stdout."""
    detection = DetectionResult(frameworks=[], risk_level="minimal")
    skipped_path = tmp_path / "raiflow.yaml"
    wr = WriteResult(path=skipped_path, action="skipped")
    summary = SummaryResult(detection=detection, write_results=[wr])

    print_summary(summary)

    captured = capsys.readouterr()
    assert str(skipped_path) in captured.out


# ── CLI integration tests ─────────────────────────────────────────────────────

def test_cli_init_help():
    """raiflow init --help exits 0 and shows --force and --directory options."""
    runner = CliRunner()
    result = runner.invoke(cli, ["init", "--help"])

    assert result.exit_code == 0
    assert "--force" in result.output
    assert "--directory" in result.output


def test_cli_init_invalid_directory():
    """raiflow init with a nonexistent directory exits 1 with an error message."""
    runner = CliRunner()
    result = runner.invoke(cli, ["init", "--directory", "/nonexistent/path/xyz"])

    assert result.exit_code == 1
