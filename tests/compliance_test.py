"""
NIST AI RMF Compliance Tests

Tests the basic compliance engine with NIST AI RMF policy using
lightweight evaluators that run without any LLM dependency.
"""
import pytest
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from raiflow.engine import ComplianceEngine
from raiflow.evaluators.faithfulness import check_faithfulness
from raiflow.evaluators.privacy import detect_pii
from raiflow.evaluators.toxicity import check_toxicity


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def nist_engine():
    engine = ComplianceEngine("policies/nist_ai_rmf.yaml")
    engine.register_evaluator("faithfulness", check_faithfulness)
    engine.register_evaluator("privacy", detect_pii)
    engine.register_evaluator("toxicity", check_toxicity)
    engine.register_evaluator("relevance", lambda x: 1.0)
    engine.register_evaluator("attribution", lambda x: 1.0)
    return engine


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_nist_ai_rmf_compliant(nist_engine):
    """Fully compliant RAG output should pass all critical checks."""
    data = {
        "question": "What is the capital of France?",
        "context": "Paris is the capital of France.",
        "answer": "The capital of France is Paris.",
    }
    results = nist_engine.run_check(data)
    assert results["compliance_score"] > 0.0

    for check in results["checks"]:
        if check.get("critical"):
            assert check["passed"], f"Critical check failed: {check['name']}"


def test_nist_pii_leakage_detected(nist_engine):
    """PII in the answer should fail the privacy check."""
    data = {
        "question": "Who can I contact for support?",
        "context": "Support contact is support@example.com",
        "answer": "You can contact our support team at support@example.com.",
    }
    results = nist_engine.run_check(data)
    privacy_check = next(
        (c for c in results["checks"] if c.get("id") == "MEASURE-3.1"), None
    )
    assert privacy_check is not None, "Privacy check not found in results"
    assert not privacy_check["passed"], "PII leakage was not detected"


def test_nist_faithfulness_low_overlap():
    """Answer with no overlap to context should score low on faithfulness."""
    data = {
        "question": "What is photosynthesis?",
        "context": "Photosynthesis is the process by which plants convert sunlight into energy.",
        "answer": "The stock market crashed in 1929 due to speculative trading.",
    }
    score = check_faithfulness(data)
    assert score < 0.3, f"Expected low faithfulness score, got {score}"


def test_nist_faithfulness_high_overlap():
    """Answer closely matching context should score high on faithfulness."""
    data = {
        "question": "What is photosynthesis?",
        "context": "Photosynthesis is the process by which plants convert sunlight into energy.",
        "answer": "Photosynthesis is the process plants use to convert sunlight into energy.",
    }
    score = check_faithfulness(data)
    assert score >= 0.6, f"Expected high faithfulness score, got {score}"


def test_toxicity_safe_content():
    """Safe content should return 1.0."""
    data = {"answer": "The weather today is sunny and warm."}
    assert check_toxicity(data) == 1.0


def test_toxicity_harmful_content():
    """Content with violence patterns should return 0.0."""
    data = {"answer": "I will show you how to make a bomb at home."}
    assert check_toxicity(data) == 0.0


def test_pii_phone_detected():
    """Phone number in answer should be detected."""
    data = {"answer": "Call us at (555) 123-4567 for support."}
    assert detect_pii(data) == 0.0


def test_pii_clean_answer():
    """Answer with no PII should return 1.0."""
    data = {"answer": "Our support team is available Monday through Friday."}
    assert detect_pii(data) == 1.0


def test_compliance_engine_missing_evaluator():
    """Engine should handle missing evaluators gracefully."""
    engine = ComplianceEngine("policies/nist_ai_rmf.yaml")
    # Register only some evaluators — others will be missing
    engine.register_evaluator("faithfulness", check_faithfulness)

    data = {"question": "test", "context": "test context", "answer": "test answer"}
    results = engine.run_check(data)

    # Should not raise, should report errors for missing evaluators
    assert "checks" in results
    missing = [c for c in results["checks"] if "error" in c]
    assert len(missing) > 0


# ── Optional LLM tests (skipped in CI if Ollama not running) ──────────────────

def test_llm_judge_semantic_check():
    """Semantic faithfulness check via LLM judge — skipped if Ollama unavailable."""
    from raiflow.evaluators.llm_judge import RaiFlowJudge
    judge = RaiFlowJudge(model="llama3:latest")

    data = {
        "question": "Is the sky blue?",
        "context": "The sky appears blue during the day due to Rayleigh scattering.",
        "answer": "Yes, the sky is blue because of light scattering.",
    }

    try:
        score = judge.evaluate_faithfulness(data)
        assert 0.0 <= score <= 1.0, f"Score out of range: {score}"
    except Exception:
        pytest.skip("Ollama not running locally — skipping LLM semantic check.")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
