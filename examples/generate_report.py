import sys
from pathlib import Path
import json

# Add the project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from raiflow.engine import ComplianceEngine
from raiflow.evaluators.faithfulness import check_faithfulness
from raiflow.evaluators.privacy import detect_pii
from raiflow.evaluators.toxicity import check_toxicity

def generate_demo_report():
    engine = ComplianceEngine("policies/nist_ai_rmf.yaml")
    engine.register_evaluator("faithfulness", check_faithfulness)
    engine.register_evaluator("privacy", detect_pii)
    engine.register_evaluator("toxicity", check_toxicity)
    engine.register_evaluator("relevance", lambda x: 0.95)
    engine.register_evaluator("attribution", lambda x: 1.0)

    # Sample RAG Data (Mildly non-compliant: high overlap but includes PII)
    demo_data = {
        "question": "What is the policy on data sharing?",
        "context": "Our policy states we protect all user data and do not share it. For questions, contact privacy@company.ai.",
        "answer": "We protect all user data. For more info, email privacy@company.ai."
    }

    results = engine.run_check(demo_data)
    
    output_path = "examples/compliance_report_demo.json"
    engine.save_report(results, output_path)
    print(f"Report saved to {output_path}")

if __name__ == "__main__":
    generate_demo_report()
