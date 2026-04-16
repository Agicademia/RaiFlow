#!/usr/bin/env python3
"""
CI/CD Compliance Check Script

This script can be used in CI/CD pipelines to:
1. Run automated compliance checks
2. Generate compliance reports
3. Fail builds if compliance thresholds are not met
4. Create audit trails for regulatory purposes
"""

import os
import sys
import json
import argparse
from datetime import datetime
from typing import Dict, List, Any

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from raiflow.engine import ComplianceEngine, DeJureComplianceEngine
from raiflow.evaluators.llm_judge import RaiFlowJudge
from raiflow.evaluators.eu_ai_act import EUAIActEvaluators

class CICDComplianceChecker:
    """Automated compliance checker for CI/CD pipelines."""
    
    def __init__(self, policy_path: str, model: str = "llama3:latest"):
        self.policy_path = policy_path
        self.model = model
        self.judge = None
        self.evaluators = None
        self.compliance_engine = None
        self.dejure_engine = None
        
    def initialize(self):
        """Initialize all compliance components."""
        print("🔧 Initializing compliance checker...")
        
        try:
            # Initialize LLM judge
            self.judge = RaiFlowJudge(model=self.model)
            print(f"  ✅ LLM Judge initialized with {self.model}")
            
            # Initialize EU AI Act evaluators
            self.evaluators = EUAIActEvaluators(self.judge)
            print(f"  ✅ EU AI Act evaluators initialized ({len(self.evaluators.get_all_evaluators())} evaluators)")
            
            # Initialize compliance engine
            self.compliance_engine = ComplianceEngine(self.policy_path)
            print(f"  ✅ Compliance engine loaded")
            
            # Initialize De Jure engine
            self.dejure_engine = DeJureComplianceEngine(self.policy_path, self.judge)
            print(f"  ✅ De Jure engine loaded")
            
            return True
            
        except Exception as e:
            print(f"  ❌ Initialization failed: {e}")
            return False
    
    def run_compliance_check(self, test_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run compliance checks on provided test data."""
        print("\n📋 Running compliance checks...")
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "model": self.model,
            "policy": self.policy_path,
            "checks": {},
            "overall_score": 0.0,
            "passed": False
        }
        
        try:
            # Run individual compliance checks
            checks = [
                ("risk_management", self.evaluators.risk_management_system_check),
                ("data_governance", self.evaluators.data_governance_check),
                ("technical_documentation", self.evaluators.technical_documentation_check),
                ("automatic_logging", self.evaluators.automatic_logging_check),
                ("transparency", self.evaluators.transparency_by_design_check),
                ("human_oversight", self.evaluators.human_oversight_design_check),
            ]
            
            scores = []
            for check_name, check_func in checks:
                try:
                    score = check_func(test_data)
                    results["checks"][check_name] = {
                        "score": score,
                        "status": "pass" if score >= 0.5 else "fail",
                        "threshold": 0.5
                    }
                    scores.append(score)
                    print(f"  ✅ {check_name}: {score:.2f} ({'PASS' if score >= 0.5 else 'FAIL'})")
                except Exception as e:
                    results["checks"][check_name] = {
                        "score": 0.0,
                        "status": "error",
                        "error": str(e)
                    }
                    print(f"  ❌ {check_name}: ERROR - {e}")
            
            # Calculate overall score
            if scores:
                results["overall_score"] = sum(scores) / len(scores)
                results["passed"] = results["overall_score"] >= 0.6
            
            print(f"\n📊 Overall Score: {results['overall_score']:.2f}")
            print(f"{'✅' if results['passed'] else '❌'} Compliance Status: {'PASS' if results['passed'] else 'FAIL'}")
            
        except Exception as e:
            print(f"  ❌ Compliance check failed: {e}")
            results["error"] = str(e)
        
        return results
    
    def run_full_audit(self, system_description: str) -> Dict[str, Any]:
        """Run a full De Jure audit on system description."""
        print("\n🔍 Running full De Jure audit...")
        
        try:
            results = self.dejure_engine.run_compliance_audit(system_description)
            print(f"  ✅ Audit completed with {len(results.get('sections', []))} sections")
            return results
        except Exception as e:
            print(f"  ❌ Audit failed: {e}")
            return {"error": str(e)}
    
    def generate_report(self, results: Dict[str, Any], output_path: str):
        """Generate a compliance report in JSON format."""
        print(f"\n📝 Generating compliance report: {output_path}")
        
        report = {
            "report_type": "EU AI Act Compliance Report",
            "generated_at": datetime.now().isoformat(),
            "framework": "RaiFlow",
            "version": "1.0.0",
            "results": results,
            "summary": {
                "total_checks": len(results.get("checks", {})),
                "passed_checks": sum(1 for c in results.get("checks", {}).values() if c.get("status") == "pass"),
                "failed_checks": sum(1 for c in results.get("checks", {}).values() if c.get("status") == "fail"),
                "overall_score": results.get("overall_score", 0),
                "compliance_status": "COMPLIANT" if results.get("passed") else "NON-COMPLIANT"
            }
        }
        
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        print(f"  ✅ Report saved to {output_path}")
        return report


def main():
    """Main function for CI/CD compliance checking."""
    parser = argparse.ArgumentParser(description="RaiFlow CI/CD Compliance Checker")
    parser.add_argument("--policy", default="policies/eu_ai_act.yaml", help="Path to policy file")
    parser.add_argument("--model", default="llama3:latest", help="LLM model to use")
    parser.add_argument("--output", default="ci_cd_compliance_report.json", help="Output report path")
    parser.add_argument("--fail-on-error", action="store_true", help="Fail build on compliance errors")
    args = parser.parse_args()
    
    print("🚀 RaiFlow CI/CD Compliance Checker")
    print("=" * 50)
    
    # Initialize checker
    checker = CICDComplianceChecker(args.policy, args.model)
    if not checker.initialize():
        print("❌ Failed to initialize compliance checker")
        sys.exit(1 if args.fail_on_error else 0)
    
    # Sample test data (in real CI/CD, this would come from your test suite)
    test_data = {
        "question": "Does your AI system comply with EU AI Act requirements?",
        "context": """
        Our AI system implements comprehensive compliance measures:
        - Risk management system covering all lifecycle stages
        - Data governance with bias detection and mitigation
        - Complete technical documentation
        - Automatic logging with traceability
        - Transparent operation with clear instructions
        - Human oversight with intervention capabilities
        """,
        "answer": "Yes, our system is designed to comply with all applicable EU AI Act requirements."
    }
    
    # Run compliance checks
    results = checker.run_compliance_check(test_data)
    
    # Generate report
    report = checker.generate_report(results, args.output)
    
    # Exit with appropriate code
    if results.get("passed"):
        print("\n✅ Compliance check PASSED")
        sys.exit(0)
    else:
        print("\n❌ Compliance check FAILED")
        if args.fail_on_error:
            sys.exit(1)
        else:
            sys.exit(0)


if __name__ == "__main__":
    main()