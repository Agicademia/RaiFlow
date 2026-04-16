import yaml
import json
from pathlib import Path
from typing import List, Dict, Any

class ComplianceEngine:
    def __init__(self, policy_path: str):
        self.policy_path = Path(policy_path)
        self.policy = self._load_policy()
        self.evaluators = {}

    def _load_policy(self) -> Dict[str, Any]:
        with open(self.policy_path, 'r') as f:
            return yaml.safe_load(f)

    def register_evaluator(self, name: str, evaluator_func):
        self.evaluators[name] = evaluator_func

    def run_check(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Runs compliance checks on input data (question, context, answer).
        """
        results = {
            "policy_name": self.policy.get("policy_name"),
            "compliance_score": 0.0,
            "checks": []
        }

        total_checks = len(self.policy.get("compliance_mappings", []))
        passed_checks = 0

        for mapping in self.policy.get("compliance_mappings", []):
            evaluator_name = mapping.get("evaluator")
            threshold = mapping.get("threshold", 0.0)
            
            if evaluator_name in self.evaluators:
                score = self.evaluators[evaluator_name](input_data)
                passed = score >= threshold
                
                check_result = {
                    "id": mapping.get("id"),
                    "name": mapping.get("name"),
                    "score": score,
                    "threshold": threshold,
                    "passed": passed,
                    "critical": mapping.get("critical", False)
                }
                
                if passed:
                    passed_checks += 1
                
                results["checks"].append(check_result)
            else:
                results["checks"].append({
                    "id": mapping.get("id"),
                    "name": mapping.get("name"),
                    "error": f"Evaluator '{evaluator_name}' not found.",
                    "passed": False
                })

        results["compliance_score"] = passed_checks / total_checks if total_checks > 0 else 0.0
        return results

    def save_report(self, results: Dict[str, Any], output_path: str):
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)

class DeJureComplianceEngine(ComplianceEngine):
    """
    Advanced Compliance Engine implementing the De Jure pipeline:
    Iterative refinement through Metadata -> Definitions -> Rules.
    """
    def __init__(self, policy_path: str, judge: Any, threshold: float = 0.75, max_retries: int = 3):
        super().__init__(policy_path)
        self.judge = judge
        self.max_retries = max_retries
        self.threshold = threshold  # Configurable: lower for local models (e.g. 0.75), 0.9 for cloud

    def run_compliance_audit(self, source_text: str, section_id: str = None) -> Dict[str, Any]:
        """
        Executes the full De Jure hierarchical audit.
        If section_id is provided, only that section from the policy is audited.
        """
        audit_report = {
            "policy": self.policy.get("policy_name"),
            "sections": []
        }

        for section in self.policy.get("regulatory_sections", []):
            if section_id and section["section_id"] != section_id:
                continue

            print(f"\n[SECTION: {section['section_id']}]")
            section_audit = {
                "section_id": section["section_id"],
                "stages": []
            }
            
            # Stage 1: Metadata
            metadata_extraction = section.get("metadata", {})
            stage_result = self._hierarchical_repair(
                "Metadata", 
                source_text, 
                metadata_extraction, 
                ["Completeness", "Fidelity", "Non-Hallucination"]
            )
            section_audit["stages"].append(stage_result)
            
            # Stage 2: Definitions
            definitions_extraction = section.get("definitions", [])
            stage_result = self._hierarchical_repair(
                "Definitions", 
                source_text, 
                {"definitions": definitions_extraction}, 
                ["Accuracy", "Non-Hallucination", "Quality of Terms"]
            )
            section_audit["stages"].append(stage_result)
            
            # Stage 3: Rules
            rules_extraction = section.get("rules", [])
            stage_result = self._hierarchical_repair(
                "Rules", 
                source_text, 
                {"rules": rules_extraction}, 
                ["Actionability", "Neutrality", "Accuracy", "Fidelity"]
            )
            section_audit["stages"].append(stage_result)
            
            audit_report["sections"].append(section_audit)
            
        return audit_report

    def _hierarchical_repair(self, stage_name: str, source: str, initial_data: Any, criteria: List[str]) -> Dict[str, Any]:
        """
        The core De Jure loop: Judge -> Score -> Repair if < threshold.
        """
        current_extraction = initial_data
        best_extraction = initial_data
        best_score = 0.0
        history = []

        print(f"  > Analyzing {stage_name}...")

        for attempt in range(self.max_retries):
            print(f"    - Attempt {attempt + 1}/{self.max_retries}...", end=" ", flush=True)
            
            judgment = self.judge.judge_step(stage_name, source, current_extraction, criteria)
            score = judgment.get("average_score", 0.0)
            critique = judgment.get("critique", "")

            print(f"Score: {round(score, 2)}")
            
            history.append({
                "attempt": attempt + 1,
                "score": round(score, 3),
                "critique": critique
            })

            if score > best_score:
                best_score = score
                best_extraction = current_extraction

            if score >= self.threshold:
                print(f"    [OK] Threshold met at {score}")
                break

            # De Jure Surgical Repair: feed critique back to generate an improved extraction
            if attempt < self.max_retries - 1:
                print(f"    [REPAIR] Surgically improving {stage_name} based on critique...")
                repaired = self.judge.repair_extraction(
                    stage_name, source, current_extraction, critique
                )
                current_extraction = repaired

        return {
            "stage": stage_name,
            "final_score": round(best_score, 3),
            "passed": best_score >= self.threshold,
            "threshold": self.threshold,
            "history": history,
            "final_extraction": best_extraction
        }
