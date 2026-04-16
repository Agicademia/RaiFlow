import os
import sys

# Ensure the project root is in sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from raiflow.engine import DeJureComplianceEngine
from raiflow.evaluators.llm_judge import RaiFlowJudge
import json

# Full source text including preamble so the judge can verify metadata fields.
ARTICLE_10_TEXT = """
REGULATION (EU) 2024/1689 OF THE EUROPEAN PARLIAMENT AND OF THE COUNCIL
of 13 June 2024 — laying down harmonised rules on artificial intelligence (Artificial Intelligence Act)
Official Journal of the European Union, L 2024/1689. Entered into force: 1 August 2024.

Article 10 — Data and data governance
1. High-risk AI systems which make use of techniques involving the training of models with data 
shall be developed on the basis of training, validation and testing datasets that meet the 
quality criteria referred to in paragraphs 2 to 5.
2. Training, validation and testing datasets shall be subject to appropriate data governance 
and management practices. Those practices shall concern in particular:
(a) the relevant design choices;
(b) data collection;
(c) relevant data preparation processing operations, such as annotation, labelling, cleaning, 
enrichment and aggregation;
(d) a prior assessment of the availability, quantity and suitability of the datasets needed.
"""

ARTICLE_13_TEXT = """
REGULATION (EU) 2024/1689 OF THE EUROPEAN PARLIAMENT AND OF THE COUNCIL
Official Journal of the European Union, L 2024/1689. Entered into force: 1 August 2024.

Article 13 — Transparency and provision of information to deployers
1. High-risk AI systems shall be designed and developed in such a way as to ensure 
that their operation is sufficiently transparent to enable deployers to interpret 
the system’s output and use it appropriately.
2. High-risk AI systems shall be accompanied by instructions for use in an appropriate 
digital format or otherwise that include concise, complete, correct and clear 
information that is relevant, accessible and comprehensible to deployers.
"""

def main():
    # Detect Cloud API Key
    api_key = os.getenv("GEMMA_API_KEY")
    
    if api_key:
        print(">>> GEMMA_API_KEY detected. Switching to Gemma 4 (Cloud)...")
        model_name = "gemma-4-31b-it"
        threshold = 0.90 
        max_retries = 2   
    else:
        print(">>> No API key found. Defaulting to local gemma2:2b (Ollama)...")
        model_name = "gemma2:2b"
        threshold = 0.75 
        max_retries = 3

    # Initialize Judge
    judge = RaiFlowJudge(model=model_name, api_key=api_key)

    # Initialize De Jure Engine with EU AI Act policy
    policy_path = os.path.join(os.path.dirname(__file__), '..', 'policies', 'eu_ai_act.yaml')
    engine = DeJureComplianceEngine(policy_path, judge, threshold=threshold, max_retries=max_retries)
    
    print(f"\n--- Starting De Jure Compliance Audit ---")
    print(f"Target Model: {model_name}")
    print(f"Config: threshold={threshold}, max_retries={max_retries}")
    print("-" * 50)
    
    # Audit mapping
    target_audits = [
        ("Article 10", ARTICLE_10_TEXT),
        ("Article 13", ARTICLE_13_TEXT)
    ]

    all_results = []
    for section_id, text in target_audits:
        res = engine.run_compliance_audit(text, section_id=section_id)
        all_results.extend(res["sections"])
    
    # Final Summary Report
    print("\n" + "="*50)
    print("FINAL COMPLIANCE SUMMARY")
    print("="*50)
    for section in all_results:
        print(f"\n[SECTION: {section['section_id']}]")
        for stage in section["stages"]:
            status = "PASS" if stage["passed"] else "FAIL"
            print(f"  Stage: {stage['stage']} | Final Score: {stage['final_score']} | Status: [{status}]")

if __name__ == "__main__":
    main()
