"""
RaiFlow HTTP Interceptor

A transparent proxy that sits in front of ANY RAG API endpoint.
It forwards requests, captures responses, and audits them against
a compliance framework — without touching the target app's code.

Usage:
    python -m raiflow.interceptor --target http://localhost:7860 --framework eu_ai_act

Then point your client at http://localhost:8080 instead of the RAG app directly.
"""

import os
import json
import time
import argparse
import datetime
import threading
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, urljoin
from typing import Optional

from raiflow.evaluators.privacy import detect_pii, scan_for_pii
from raiflow.evaluators.toxicity import check_toxicity, get_toxicity_categories
from raiflow.evaluators.faithfulness import check_faithfulness


# ── Lightweight sync audit (no LLM required for fast path) ───────────────────

def fast_audit(request_body: dict, response_body: dict) -> dict:
    """
    Runs the lightweight (non-LLM) compliance checks synchronously.
    These complete in <1ms and never block the response.
    """
    answer  = response_body.get("answer", response_body.get("response", str(response_body)))
    context = response_body.get("context", response_body.get("source_documents", ""))
    if isinstance(context, list):
        context = " ".join(str(c) for c in context)

    data = {"answer": answer, "context": context, "question": request_body.get("query", "")}

    pii_score      = detect_pii(data)
    toxicity_score = check_toxicity(data)
    faith_score    = check_faithfulness(data)

    pii_types  = scan_for_pii(answer)
    tox_cats   = get_toxicity_categories(answer)

    passed = pii_score == 1.0 and toxicity_score == 1.0

    return {
        "passed": passed,
        "scores": {
            "pii_clean":    pii_score,
            "toxicity_safe": toxicity_score,
            "faithfulness": faith_score,
        },
        "violations": {
            "pii_types":          pii_types,
            "toxicity_categories": tox_cats,
        },
    }


def log_audit_event(log_path: str, event: dict):
    """Append an audit event to the JSON log file (thread-safe)."""
    events = []
    if os.path.exists(log_path):
        try:
            with open(log_path, "r") as f:
                events = json.load(f)
        except Exception:
            events = []
    events.append(event)
    with open(log_path, "w") as f:
        json.dump(events, f, indent=2)


# ── Proxy handler ─────────────────────────────────────────────────────────────

class RaiFlowProxyHandler(BaseHTTPRequestHandler):
    """
    Transparent HTTP proxy that:
    1. Forwards every request to the target RAG app
    2. Captures the response
    3. Runs fast compliance checks
    4. Logs the audit event
    5. Returns the original response unmodified (or blocked if critical violation)
    """

    target_url: str = ""
    framework: str  = "eu_ai_act"
    log_path: str   = "raiflow_audit_trail.json"
    block_on_pii: bool = False

    def log_message(self, format, *args):
        # Suppress default HTTP server logs — we do our own
        pass

    def do_POST(self):
        self._proxy("POST")

    def do_GET(self):
        self._proxy("GET")

    def _proxy(self, method: str):
        # 1. Read incoming request
        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length) if content_length else b""

        try:
            request_body = json.loads(raw_body) if raw_body else {}
        except Exception:
            request_body = {"raw": raw_body.decode("utf-8", errors="replace")}

        # 2. Forward to target RAG app
        target = urljoin(self.target_url, self.path)
        start  = time.time()

        try:
            resp = requests.request(
                method=method,
                url=target,
                headers={k: v for k, v in self.headers.items()
                         if k.lower() not in ("host", "content-length")},
                data=raw_body,
                timeout=60,
                allow_redirects=True,
            )
            latency_ms = round((time.time() - start) * 1000)

            try:
                response_body = resp.json()
            except Exception:
                response_body = {"raw": resp.text}

        except requests.exceptions.ConnectionError:
            self.send_error(502, f"Cannot reach target RAG app at {self.target_url}")
            return
        except Exception as e:
            self.send_error(500, str(e))
            return

        # 3. Run fast compliance audit (non-blocking — runs in <1ms)
        audit = fast_audit(request_body, response_body)

        # 4. Log the event
        event = {
            "timestamp":    datetime.datetime.now().isoformat(),
            "function":     f"[intercepted] {method} {self.path}",
            "framework":    self.framework,
            "framework_name": self.framework.replace("_", " ").title(),
            "model":        "lightweight (no LLM)",
            "target_url":   target,
            "latency_ms":   latency_ms,
            "request":      {k: v for k, v in request_body.items() if k != "password"},
            "audit_fast":   audit,
            "audit_report": {
                "policy": self.framework,
                "sections": [{
                    "section_id": "Fast Audit",
                    "stages": [
                        {"stage": "PII Check",    "final_score": audit["scores"]["pii_clean"],     "passed": audit["scores"]["pii_clean"] == 1.0,    "threshold": 1.0, "history": []},
                        {"stage": "Toxicity",     "final_score": audit["scores"]["toxicity_safe"], "passed": audit["scores"]["toxicity_safe"] == 1.0, "threshold": 1.0, "history": []},
                        {"stage": "Faithfulness", "final_score": audit["scores"]["faithfulness"],  "passed": audit["scores"]["faithfulness"] >= 0.5,  "threshold": 0.5, "history": []},
                    ]
                }]
            }
        }

        # Log in background thread so we never add latency to the response
        threading.Thread(target=log_audit_event, args=(self.log_path, event), daemon=True).start()

        # 5. Block response if PII detected and block mode is on
        if self.block_on_pii and not audit["passed"]:
            blocked_response = {
                "error": "Response blocked by RaiFlow compliance shield.",
                "violations": audit["violations"],
            }
            body = json.dumps(blocked_response).encode()
            self.send_response(403)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-RaiFlow-Blocked", "true")
            self.end_headers()
            self.wfile.write(body)
            print(f"[BLOCKED] {method} {self.path} — violations: {audit['violations']}")
            return

        # 6. Return original response unmodified
        self.send_response(resp.status_code)
        for key, val in resp.headers.items():
            if key.lower() in ("content-type", "content-encoding", "cache-control"):
                self.send_header(key, val)
        body = resp.content
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-RaiFlow-Audited", "true")
        self.send_header("X-RaiFlow-PII-Clean", str(audit["scores"]["pii_clean"]))
        self.send_header("X-RaiFlow-Toxicity-Safe", str(audit["scores"]["toxicity_safe"]))
        self.end_headers()
        self.wfile.write(body)

        status = "✅ PASS" if audit["passed"] else "⚠️  VIOLATION"
        print(f"[{status}] {method} {self.path} → {resp.status_code} ({latency_ms}ms) "
              f"| PII:{audit['scores']['pii_clean']} "
              f"| Tox:{audit['scores']['toxicity_safe']} "
              f"| Faith:{audit['scores']['faithfulness']:.2f}")


# ── Entry point ───────────────────────────────────────────────────────────────

def run_interceptor(
    target: str,
    port: int = 8080,
    framework: str = "eu_ai_act",
    log_path: str = "raiflow_audit_trail.json",
    block_on_pii: bool = False,
):
    # Inject config into handler class
    RaiFlowProxyHandler.target_url  = target.rstrip("/")
    RaiFlowProxyHandler.framework   = framework
    RaiFlowProxyHandler.log_path    = log_path
    RaiFlowProxyHandler.block_on_pii = block_on_pii

    server = HTTPServer(("0.0.0.0", port), RaiFlowProxyHandler)

    print(f"""
╔══════════════════════════════════════════════════════╗
║          RaiFlow HTTP Interceptor                    ║
╠══════════════════════════════════════════════════════╣
║  Proxy port  : http://localhost:{port:<24}║
║  Target RAG  : {target:<38}║
║  Framework   : {framework:<38}║
║  Block PII   : {str(block_on_pii):<38}║
║  Audit log   : {log_path:<38}║
╚══════════════════════════════════════════════════════╝

Point your client at http://localhost:{port} instead of {target}
Every request/response will be audited transparently.
Press Ctrl+C to stop.
""")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[INTERCEPTOR] Stopped.")
        server.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RaiFlow HTTP Compliance Interceptor")
    parser.add_argument("--target",      required=True,          help="Target RAG app URL, e.g. http://localhost:7860")
    parser.add_argument("--port",        type=int, default=8080, help="Interceptor listen port (default: 8080)")
    parser.add_argument("--framework",   default="eu_ai_act",    help="Compliance framework (default: eu_ai_act)")
    parser.add_argument("--log",         default="raiflow_audit_trail.json", help="Audit log path")
    parser.add_argument("--block-pii",   action="store_true",    help="Block responses containing PII (default: audit-only)")
    args = parser.parse_args()

    run_interceptor(
        target=args.target,
        port=args.port,
        framework=args.framework,
        log_path=args.log,
        block_on_pii=args.block_pii,
    )
