"""
RaiFlow Final Readiness Assessment

Runs a comprehensive end-to-end check of the RaiFlow framework:
- Policy files present and valid
- All 26 EU AI Act evaluators registered
- NIST AI RMF evaluators registered
- Lightweight evaluators (privacy, toxicity, faithfulness) working
- Project analyzer working
- Server endpoints importable
- CI/CD workflow present

Run with: python examples/final_assessment.py
"""
import sys
import os
import json
import yaml
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


def check(label: str, passed: bool, detail: str = ""):
    status = "PASS" if passed else "FAIL"
    suffix = f"  ({detail})" if detail else ""
    print(f"  [{status}] {label}{suffix}")
    return passed


def section(title: str):
    print(f"\n{'─'*55}")
    print(f"  {title}")
    print(f"{'─'*55}")


results = []

# ── 1. Policy Files ───────────────────────────────────────────────────────────
section("1. Policy Files")

eu_yaml = ROOT / "policies" / "eu_ai_act.yaml"
nist_yaml = ROOT / "policies" / "nist_ai_rmf.yaml"

results.append(check("eu_ai_act.yaml exists", eu_yaml.exists()))
results.append(check("nist_ai_rmf.yaml exists", nist_yaml.exists()))

if eu_yaml.exists():
    with open(eu_yaml) as f:
        policy = yaml.safe_load(f)
    sections_found = [s["section_id"] for s in policy.get("regulatory_sections", [])]
    for art in ["Article 9", "Article 10", "Article 11", "Article 12", "Article 13", "Article 14"]:
        results.append(check(f"  {art} present in policy", art in sections_found))

# ── 2. EU AI Act Evaluators ───────────────────────────────────────────────────
section("2. EU AI Act Evaluators (26 checks)")

try:
    from raiflow.evaluators.eu_ai_act import EUAIActEvaluators
    from raiflow.evaluators.llm_judge import RaiFlowJudge

    judge = RaiFlowJudge(model="gemma2:2b")
    evals = EUAIActEvaluators(judge)
    all_evals = evals.get_all_evaluators()
    results.append(check("EUAIActEvaluators instantiated", True))
    results.append(check(f"≥26 evaluators registered", len(all_evals) >= 26, f"found {len(all_evals)}"))
except Exception as e:
    results.append(check("EUAIActEvaluators", False, str(e)))

# ── 3. NIST AI RMF Evaluators ─────────────────────────────────────────────────
section("3. NIST AI RMF Evaluators")

try:
    from raiflow.evaluators.nist_ai_rmf import NISTAIRMFEvaluators
    nist_evals = NISTAIRMFEvaluators(judge)
    all_nist = nist_evals.get_all_evaluators()
    results.append(check("NISTAIRMFEvaluators instantiated", True))
    results.append(check(f"8 evaluators registered", len(all_nist) == 8, f"found {len(all_nist)}"))
except Exception as e:
    results.append(check("NISTAIRMFEvaluators", False, str(e)))

# ── 4. Lightweight Evaluators ─────────────────────────────────────────────────
section("4. Lightweight Evaluators (no LLM required)")

try:
    from raiflow.evaluators.privacy import detect_pii, scan_for_pii
    from raiflow.evaluators.toxicity import check_toxicity, get_toxicity_categories
    from raiflow.evaluators.faithfulness import check_faithfulness

    # Privacy
    pii_score = detect_pii({"answer": "Contact us at test@example.com"})
    results.append(check("PII detection (email)", pii_score == 0.0, f"score={pii_score}"))

    clean_score = detect_pii({"answer": "Our team is available Monday to Friday."})
    results.append(check("PII clean pass", clean_score == 1.0, f"score={clean_score}"))

    # Toxicity
    safe_score = check_toxicity({"answer": "The weather is sunny today."})
    results.append(check("Toxicity safe content", safe_score == 1.0, f"score={safe_score}"))

    # Faithfulness
    faith_score = check_faithfulness({
        "context": "Paris is the capital of France.",
        "answer": "The capital of France is Paris.",
    })
    results.append(check("Faithfulness high overlap", faith_score >= 0.5, f"score={faith_score:.2f}"))

except Exception as e:
    results.append(check("Lightweight evaluators", False, str(e)))

# ── 5. Compliance Engine ──────────────────────────────────────────────────────
section("5. Compliance Engine")

try:
    from raiflow.engine import ComplianceEngine, DeJureComplianceEngine
    engine = ComplianceEngine(str(eu_yaml))
    results.append(check("ComplianceEngine loads EU AI Act policy", True))
    results.append(check("Policy name correct", engine.policy.get("policy_name") == "EU Artificial Intelligence Act"))
except Exception as e:
    results.append(check("ComplianceEngine", False, str(e)))

# ── 6. Framework Registry ─────────────────────────────────────────────────────
section("6. Framework Registry")

try:
    from raiflow.framework_registry import list_available_frameworks, select_framework
    frameworks = list_available_frameworks()
    ids = [f.id for f in frameworks]
    results.append(check("eu_ai_act registered", "eu_ai_act" in ids))
    results.append(check("nist_ai_rmf registered", "nist_ai_rmf" in ids))
except Exception as e:
    results.append(check("Framework Registry", False, str(e)))

# ── 7. Project Analyzer ───────────────────────────────────────────────────────
section("7. Project Analyzer")

try:
    from raiflow.analyzer import ProjectAnalyzer
    analyzer = ProjectAnalyzer()
    info = analyzer.analyze_directory(str(ROOT))
    results.append(check("ProjectAnalyzer runs", True))
    results.append(check("Detects LLM usage", info.has_llm))
    results.append(check("Generates summary", len(info.analysis_summary) > 0))
except Exception as e:
    results.append(check("ProjectAnalyzer", False, str(e)))

# ── 8. Server Imports ─────────────────────────────────────────────────────────
section("8. Server & Dashboard")

try:
    import importlib.util
    spec = importlib.util.spec_from_file_location("server", ROOT / "server.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    results.append(check("server.py imports cleanly", True))
    results.append(check("/api/health endpoint defined", hasattr(mod, 'health_check')))
    results.append(check("/api/frameworks endpoint defined", hasattr(mod, 'list_frameworks')))
except Exception as e:
    results.append(check("server.py", False, str(e)))

dashboard_html = ROOT / "raiflow" / "dashboard" / "index.html"
dashboard_js   = ROOT / "raiflow" / "dashboard" / "src" / "main.js"
results.append(check("Dashboard index.html exists", dashboard_html.exists()))
results.append(check("Dashboard main.js exists", dashboard_js.exists()))

# ── 9. CI/CD & Tests ─────────────────────────────────────────────────────────
section("9. CI/CD & Tests")

results.append(check("tests/compliance_test.py exists", (ROOT / "tests" / "compliance_test.py").exists()))
results.append(check("tests/eu_ai_act_test.py exists", (ROOT / "tests" / "eu_ai_act_test.py").exists()))
results.append(check("tests/conftest.py exists", (ROOT / "tests" / "conftest.py").exists()))
results.append(check(".github/ directory exists", (ROOT / ".github").exists()))

# ── Final Score ───────────────────────────────────────────────────────────────
passed = sum(results)
total  = len(results)
pct    = round((passed / total) * 100, 1)

print(f"\n{'='*55}")
print(f"  FINAL READINESS SCORE: {passed}/{total} checks passed ({pct}%)")
print(f"{'='*55}\n")

if pct >= 85:
    print("  Status: PRODUCTION READY ✅")
elif pct >= 70:
    print("  Status: MOSTLY COMPLETE — minor gaps remain ⚠️")
else:
    print("  Status: INCOMPLETE — significant work needed ❌")

print()
