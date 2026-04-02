import pytest
import sys
from pathlib import Path

# Add the project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from raiflow.engine import ComplianceEngine
from raiflow.evaluators.faithfulness import check_faithfulness
from raiflow.evaluators.privacy import detect_pii
from raiflow.evaluators.toxicity import check_toxicity

def test_nist_ai_rmf_compliance():
    # Load the policy
    policy_path = "policies/nist_ai_rmf.yaml"
    engine = ComplianceEngine(policy_path)

    # Register evaluators
    engine.register_evaluator("faithfulness", check_faithfulness)
    engine.register_evaluator("privacy", detect_pii)
    engine.register_evaluator("toxicity", check_toxicity)
    # Mock remaining evaluators for now
    engine.register_evaluator("relevance", lambda x: 1.0)
    engine.register_evaluator("attribution", lambda x: 1.0)

    # Mock RAG output (COMPLIANT)
    compliant_data = {
        "question": "What is the capital of France?",
        "context": "Paris is the capital of France.",
        "answer": "The capital of France is Paris."
    }

    results = engine.run_check(compliant_data)
    print("\n[Compliant Data Results]")
    print(results)
    
    # Assert that all critical checks passed
    for check in results["checks"]:
        if check.get("critical"):
            assert check["passed"], f"Critical check failed: {check['name']}"

def test_non_compliant_pii_leakage():
    policy_path = "policies/nist_ai_rmf.yaml"
    engine = ComplianceEngine(policy_path)
    engine.register_evaluator("privacy", detect_pii)
    engine.register_evaluator("faithfulness", lambda x: 1.0)
    engine.register_evaluator("toxicity", lambda x: 1.0)
    engine.register_evaluator("relevance", lambda x: 1.0)
    engine.register_evaluator("attribution", lambda x: 1.0)

    # Mock RAG output (NON-COMPLIANT - PII Leakage)
    non_compliant_data = {
        "question": "Who can I contact for support?",
        "context": "Support contact is vaibhav@example.com",
        "answer": "You can contact our support team at vaibhav@example.com."
    }

    results = engine.run_check(non_compliant_data)
    print("\n[Non-Compliant PII Results]")
    print(results)

    # Check if privacy check failed
    privacy_check = next(c for c in results["checks"] if c["id"] == "MEASURE-3.1")
    assert not privacy_check["passed"], "PII leakage was not detected!"

if __name__ == "__main__":
    pytest.main([__file__])
