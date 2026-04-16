"""
Shared pytest configuration and fixtures.

Provides a mock LLM judge for CI/CD environments where Ollama/Gemini
is not available, ensuring tests pass without any LLM dependency.
"""
import os
import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.append(str(Path(__file__).parent.parent))


def _mock_query_model(prompt: str) -> str:
    """Returns a realistic-looking JSON score based on prompt content."""
    prompt_lower = prompt.lower()

    # Detect non-compliant scenarios by looking for thin context
    thin_context_signals = [
        "we test the system before release",
        "we use standard datasets",
        "the system runs automatically",
        "we sometimes save errors",
        "humans can turn it off",
        "some basic testing",
    ]
    is_thin = any(sig in prompt_lower for sig in thin_context_signals)

    score = 0.3 if is_thin else 0.82
    return f'{{"score": {score}, "reasoning": "Mock evaluation for CI/CD testing."}}'


def _mock_judge_step(stage_name, source, extraction, criteria):
    """Returns a mock judge step result."""
    return {
        "average_score": 0.80,
        "critique": "Mock critique: extraction looks reasonable.",
        "per_criterion_scores": {c: 0.80 for c in criteria},
    }


def _mock_repair_extraction(stage_name, source, current_extraction, critique):
    """Returns the extraction unchanged (no repair needed in mock)."""
    return current_extraction


@pytest.fixture(autouse=False)
def mock_llm_judge():
    """
    Fixture that patches RaiFlowJudge to avoid real LLM calls.
    Use this in tests that don't need real LLM evaluation.
    """
    with patch("raiflow.evaluators.llm_judge.RaiFlowJudge._query_model", side_effect=_mock_query_model), \
         patch("raiflow.evaluators.llm_judge.RaiFlowJudge.judge_step", side_effect=_mock_judge_step), \
         patch("raiflow.evaluators.llm_judge.RaiFlowJudge.repair_extraction", side_effect=_mock_repair_extraction):
        yield


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "llm: mark test as requiring a live LLM (Ollama or Gemini API)")
    config.addinivalue_line("markers", "integration: mark test as an integration test")
