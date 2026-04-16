"""
RaiFlow — Real RAG Integration Examples

Shows three patterns for auditing real RAG systems:

  Pattern 1: @shield on a LangChain-style RAG function
  Pattern 2: HTTP Interceptor against any running RAG API
  Pattern 3: Direct audit of a live API response

Run: python examples/real_rag_integration.py --pattern 1
"""

import os
import sys
import json
import argparse
import requests

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from raiflow import shield
from raiflow.evaluators.privacy import detect_pii, scan_for_pii
from raiflow.evaluators.toxicity import check_toxicity
from raiflow.evaluators.faithfulness import check_faithfulness


# ─────────────────────────────────────────────────────────────────────────────
# PATTERN 1: @shield decorator on a real Ollama-backed RAG function
#
# Requirements: Ollama running locally with any model pulled
#   ollama pull gemma2:2b   (or llama3, mistral, etc.)
# ─────────────────────────────────────────────────────────────────────────────

OLLAMA_URL = "http://localhost:11434/api/generate"

def _call_ollama(prompt: str, model: str = "gemma2:2b") -> str:
    """Call a local Ollama model and return the response text."""
    try:
        resp = requests.post(OLLAMA_URL, json={
            "model": model,
            "prompt": prompt,
            "stream": False,
        }, timeout=60)
        resp.raise_for_status()
        return resp.json().get("response", "")
    except requests.exceptions.ConnectionError:
        return "[ERROR] Ollama not running. Start it with: ollama serve"
    except Exception as e:
        return f"[ERROR] {e}"


@shield(framework="eu_ai_act", max_retries=1)
def ollama_rag_pipeline(query: str, context_docs: list = None) -> dict:
    """
    A real RAG pipeline backed by a local Ollama model.
    The @shield decorator audits the output against the EU AI Act.
    """
    # Simulate retrieved context (in a real app this comes from a vector DB)
    if context_docs is None:
        context_docs = [
            "Article 10 of the EU AI Act requires high-risk AI systems to use "
            "training data subject to appropriate data governance practices.",
            "Providers must ensure datasets are relevant, representative, and "
            "free from errors that could lead to discriminatory outcomes.",
        ]

    context = "\n".join(context_docs)
    prompt  = f"""Answer the question using only the provided context.

Context:
{context}

Question: {query}

Answer:"""

    answer = _call_ollama(prompt)

    return {
        "answer":  answer,
        "context": context,
        "query":   query,
        "model":   "gemma2:2b (local Ollama)",
    }


def run_pattern_1():
    print("\n" + "="*60)
    print("PATTERN 1: @shield on a local Ollama RAG pipeline")
    print("="*60)

    queries = [
        "What data governance requirements apply to high-risk AI?",
        "Can I use any dataset I want for training?",
    ]

    for q in queries:
        print(f"\nQuery: {q}")
        result = ollama_rag_pipeline(q)
        if "ERROR" not in result.get("answer", ""):
            print(f"Answer: {result['answer'][:200]}...")
        else:
            print(result["answer"])

    print("\n✅ Audit events written to raiflow_audit_trail.json")
    print("   Open http://localhost:8000 to see them in the dashboard.")


# ─────────────────────────────────────────────────────────────────────────────
# PATTERN 2: HTTP Interceptor — audit any RAG API without touching its code
#
# This starts the RaiFlow interceptor proxy in front of a target RAG app.
# Point your client at localhost:8080 instead of the real app.
# ─────────────────────────────────────────────────────────────────────────────

def run_pattern_2(target: str = "http://localhost:11434", port: int = 8080):
    print("\n" + "="*60)
    print("PATTERN 2: HTTP Interceptor (transparent proxy)")
    print("="*60)
    print(f"\nStarting RaiFlow interceptor...")
    print(f"  Proxy:  http://localhost:{port}")
    print(f"  Target: {target}")
    print(f"\nAll traffic to localhost:{port} will be:")
    print(f"  1. Forwarded to {target}")
    print(f"  2. Audited for PII, toxicity, faithfulness")
    print(f"  3. Logged to raiflow_audit_trail.json")
    print(f"\nExample — instead of calling your RAG app directly:")
    print(f"  curl http://localhost:{port}/api/generate -d '{{\"model\":\"gemma2:2b\",\"prompt\":\"...\"}}'")
    print(f"\nPress Ctrl+C to stop.\n")

    from raiflow.interceptor import run_interceptor
    run_interceptor(target=target, port=port, framework="eu_ai_act", block_on_pii=False)


# ─────────────────────────────────────────────────────────────────────────────
# PATTERN 3: Direct audit of any API response
#
# You already have a RAG app running somewhere. You just want to audit
# a specific response without changing anything.
# ─────────────────────────────────────────────────────────────────────────────

def run_pattern_3():
    print("\n" + "="*60)
    print("PATTERN 3: Direct audit of any API response")
    print("="*60)

    # Simulate responses from real-world RAG systems
    # (replace these with actual API calls to your system)
    test_cases = [
        {
            "name": "Clean response",
            "data": {
                "question": "What is the EU AI Act?",
                "context":  "The EU AI Act is a regulation establishing rules for AI systems in the EU.",
                "answer":   "The EU AI Act establishes harmonised rules for artificial intelligence systems.",
            }
        },
        {
            "name": "PII leak (email in answer)",
            "data": {
                "question": "Who should I contact?",
                "context":  "Contact the DPO at privacy@company.eu for data requests.",
                "answer":   "You should contact privacy@company.eu for all data-related requests.",
            }
        },
        {
            "name": "Hallucination (answer not grounded in context)",
            "data": {
                "question": "What is the penalty for non-compliance?",
                "context":  "The EU AI Act establishes rules for high-risk AI systems.",
                "answer":   "Non-compliance results in fines up to 35 million euros or 7% of global turnover.",
            }
        },
        {
            "name": "Toxic content",
            "data": {
                "question": "How do I get access?",
                "context":  "Access is granted by the system administrator.",
                "answer":   "I will show you how to hack the system and bypass authentication.",
            }
        },
    ]

    print(f"\n{'Case':<35} {'PII':>6} {'Toxic':>6} {'Faith':>6} {'Status':>10}")
    print("-" * 70)

    for case in test_cases:
        d = case["data"]
        pii   = detect_pii(d)
        tox   = check_toxicity(d)
        faith = check_faithfulness(d)
        ok    = pii == 1.0 and tox == 1.0

        pii_str   = "✅" if pii == 1.0   else "❌ PII"
        tox_str   = "✅" if tox == 1.0   else "❌ Toxic"
        faith_str = f"{faith:.2f}"
        status    = "PASS" if ok else "FAIL"

        print(f"{case['name']:<35} {pii_str:>6} {tox_str:>8} {faith_str:>6} {status:>10}")

        if pii < 1.0:
            print(f"  → PII detected: {scan_for_pii(d['answer'])}")

    print("\n✅ No LLM required — these checks run in <1ms.")
    print("   For deep EU AI Act article-level checks, use @shield or dejure_demo.py")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RaiFlow Real RAG Integration Examples")
    parser.add_argument("--pattern", type=int, choices=[1, 2, 3], default=3,
                        help="1=Ollama @shield, 2=HTTP interceptor, 3=Direct audit")
    parser.add_argument("--target", default="http://localhost:11434",
                        help="Target RAG app URL for pattern 2")
    parser.add_argument("--port", type=int, default=8080,
                        help="Interceptor port for pattern 2")
    args = parser.parse_args()

    if args.pattern == 1:
        run_pattern_1()
    elif args.pattern == 2:
        run_pattern_2(target=args.target, port=args.port)
    elif args.pattern == 3:
        run_pattern_3()
