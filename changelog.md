# Changelog

All notable changes to the `raiflow` project are documented here.

---

## [0.3.0] - 2026-04 (current)

### Added — Developer Dashboard
- New single-file SPA at `raiflow/dashboard/index.html` — dark theme, RaiFlow branding, all CSS/JS inlined
- `POST /api/run` endpoint on `DashboardServer` — browser-initiated compliance runs, returns 202/409/422
- `RunState` gains `"idle"` default status and `reset()` method for re-runs
- `--no-dashboard` flag on `raiflow check` — explicit headless mode
- `raiflow check` (no flags) now opens the dashboard automatically in non-CI environments
- Live ScoreBanner with Overall Score, Risk Level (Low/Medium/High/Critical), checks run, violations
- Per-article ArticleCards with pass/fail/skipped badges, scores, thresholds, and remediation hints
- "Copy remediation hint" button on failed cards
- "⬇ Download Report" button in topbar — downloads `raiflow-report-<timestamp>.json` after run completes
- LiveFeed auto-scrolling log with colour-coded entries (green/red/muted/amber)
- Page reload recovery — fetches `/api/run-state` and replays results on reconnect
- Empty-state prompt when no run has been executed yet

### Fixed
- `policies/eu_ai_act.yaml` bundled inside the `raiflow` package (`raiflow/data/eu_ai_act.yaml`) so `raiflow check` works from any directory after `pip install raiflow`
- `NameError: name 'Path' is not defined` in `gate.py` after import refactor
- `--dashboard` flag in CI now emits a single warning to stderr instead of silently proceeding

---

## [0.2.0] - 2026-04

### Added — Live Dashboard (SSE streaming)
- `DashboardServer` — FastAPI server serving `raiflow/dashboard/index.html` with SSE streaming
- `GET /api/events` — Server-Sent Events endpoint streaming `check_result`, `run_complete`, `run_error` events
- `GET /api/run-state` — returns accumulated `RunState` as JSON for late-connecting browsers
- `--dashboard` flag on `raiflow check` — starts server and opens browser automatically
- `--dashboard-port` option (default 8000, auto-increments on conflict)
- Keep-alive `: ping` comments every 15 seconds to prevent proxy timeouts
- CI environment detection — `--dashboard` silently ignored when `CI` env var set or no TTY
- Dashboard LiveFeed and Heatmap update in real-time as SSE events arrive
- Server stays alive after run completes for report exploration

---

## [0.1.5] - 2026-04

### Added — `raiflow init` (zero-friction onboarding)
- `raiflow init` CLI subcommand — scans project for AI framework imports and scaffolds compliance files
- Project scanner detects: `langchain`, `openai`, `ollama`, `llama_index`, `transformers`, `anthropic`, `google.generativeai`, `fastapi`, `haystack`, `autogen`, `crewai`, `semantic_kernel`
- Auto-infers EU AI Act risk level (`high` / `limited` / `minimal`) from detected frameworks
- Generates pre-filled `raiflow.yaml` with inline comments on every field
- Generates `.github/workflows/rai-compliance.yml` from bundled template
- `--force` flag to overwrite existing scaffold files
- `--directory` option to scaffold a non-current directory
- Idempotent — re-running without `--force` leaves existing files unchanged
- Interactive LLM setup wizard (static-only or Ollama/API key backend)
- Summary output listing detected frameworks, inferred risk level, written files, and next steps

---

## [0.1.0] - 2026-04

### Added — CI/CD Compliance Gate
- `raiflow check` CLI command with `--stage` flag (`pre-commit`, `ci`, `pre-deploy`, `post-deploy`)
- `raiflow.yaml` compliance manifest — declares system name, risk level, articles, model metadata, oversight endpoints, logging, data governance, robustness config
- Static compliance checks for EU AI Act Articles 9–14:
  - **Article 9** — Risk management: verifies `risk_management.assessment_path` exists
  - **Article 10** — Data governance: bias detection on declared dataset; robustness/toxicity checks on red-team prompts
  - **Article 12** — Logging: verifies `logging.middleware_active` is `true`
  - **Article 13** — Transparency: verifies `model_metadata.disclosure_flag` is `true`
  - **Article 14** — Human oversight: verifies override endpoints declared in manifest
  - **Banned models** — scans manifest for model identifiers on a configurable blocklist
- `CheckResult` dataclass with `article_id`, `rule_id`, `check_name`, `status`, `score`, `threshold`, `remediation_hint`
- Structured JSON compliance report (`raiflow-report.json`) with `schema_version`, `generated_at`, `git_sha`, `overall_status`, per-check results
- `--dry-run` flag — runs all checks but always exits 0
- `--threshold` flag — overrides per-rule pass threshold
- `--enable-llm-checks` flag — enables semantic LLM-based evaluators via Ollama or API
- `raiflow generate-tests` — generates pytest files from policy YAML rules
- GitHub Actions workflow template with four jobs: `pre-commit-checks`, `compliance-gate`, `build-and-sign`, `deploy-gate`
- Deploy gate blocks deployment on failure; `COMPLIANCE_NOTIFY_EMAIL` writes `raiflow-notify.json`
- `policies/eu_ai_act.yaml` — full EU AI Act Articles 9–14 rule mapping

---

## [0.0.1] - 2026-04

### Added — Pilot release
- Core `ComplianceEngine` mapping policy IDs to technical evaluators
- Initial policy mapping for NIST AI RMF 1.0
- Evaluators: Faithfulness (word-overlap), PII Detection (regex), Toxicity (keyword)
- `DeJureComplianceEngine` — iterative LLM-as-a-judge loop with surgical repair
- EU AI Act evaluators for Articles 9–14 (27 specialised checks)
- RaiFlow HTTP Interceptor — transparent proxy for auditing RAG API endpoints
- `@shield` decorator for function-level compliance enforcement
- Project Analyzer — static analysis for AI component detection
- De Jure Ingestor — converts PDF regulation text to RaiFlow YAML policies
- Jupyter notebook walkthrough (`raiflow_compliance_walkthrough.ipynb`)
- GitHub Actions CI pipeline
