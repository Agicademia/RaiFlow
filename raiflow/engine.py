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
