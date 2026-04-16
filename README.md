<div align="center">

<img src="raiflow\dashboard\raiflow-banner.png" alt="RaiFlow Logo"/>

# Regulatory Compliance Gate for AI/ML Projects

[![PyPI version](https://img.shields.io/pypi/v/raiflow.svg?color=blue)](https://pypi.org/project/raiflow/)
[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![EU AI Act](https://img.shields.io/badge/EU_AI_Act-2024%2F1689-purple.svg)](https://eur-lex.europa.eu/eli/reg/2024/1689/oj)

**One command to scaffold, check, and enforce EU AI Act compliance across your entire CI/CD pipeline.**
</div>


```bash

pip install raiflow
raiflow init            # scan project, generate raiflow.yaml + GitHub Actions workflow
raiflow check           # open live compliance dashboard in browser

```


---

## What is RaiFlow?

RaiFlow is a developer tool that enforces EU AI Act compliance (Articles 9–14) at every stage of your AI project's delivery pipeline from pre-commit hooks to production deployments.

It works by scanning your project, generating a compliance manifest (`raiflow.yaml`), running static checks against that manifest, and streaming results to a live browser dashboard. In CI environments it runs headlessly and blocks deployments on failure.

---

## Quick Start

```bash
# Install
pip install raiflow

# In your AI project directory
raiflow init                             # scaffold raiflow.yaml + .github/workflows/rai-compliance.yml
raiflow check --stage ci                 # open dashboard, run all checks
raiflow check --stage ci --no-dashboard  # headless, for CI
```

---

## How it works

```
┌─────────────────────────────────────────────────────────────────┐
│  Developer machine                                              │
│                                                                 │
│  raiflow init                                                   │
│  ├── scans .py files for AI framework imports                   │
│  ├── infers EU AI Act risk level (high / limited / minimal)     │
│  ├── writes raiflow.yaml (pre-filled, commented)                │
│  └── writes .github/workflows/rai-compliance.yml                │
│                                                                 │
│  raiflow check --stage ci                                       │
│  ├── loads raiflow.yaml                                         │
│  ├── runs 7 static compliance checks (Articles 9–14)            │
│  ├── streams results to browser dashboard via SSE               │
│  └── writes raiflow-report.json                                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  GitHub Actions (auto-configured by raiflow init)               │
│                                                                 │
│  pre-commit-checks  →  compliance-gate  →  build-and-sign       │
│                                        →  deploy-gate           │
│                                                                 │
│  Blocks merges and deployments on compliance failure            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Compliance Checks

RaiFlow runs static checks against your `raiflow.yaml` manifest for each EU AI Act article:

| Check | Article | What it verifies |
|---|---|---|
| Banned Model Scan | Internal | Model identifier not on blocklist |
| Transparency by Design | Article 13 | `model_metadata.disclosure_flag: true` |
| Risk Management Documentation | Article 9 | Risk assessment document exists at declared path |
| Human Oversight Endpoints | Article 14 | Override/halt endpoints declared in manifest |
| Logging Middleware Active | Article 12 | `logging.middleware_active: true` |
| Bias Detection | Article 10 | Dataset scanned for protected attribute bias |
| Robustness/Toxicity Check | Article 10 | Red-team prompts tested for toxic outputs |

Each check returns a `CheckResult` with `status` (pass/fail/skipped), `score`, `threshold`, and a `remediation_hint` explaining exactly what to fix.

---

## Pipeline Stages

| Stage | Checks | Use case |
|---|---|---|
| `pre-commit` | Banned Model Scan | Fast local check before every commit |
| `ci` | All 7 checks | Pull request gate |
| `pre-deploy` | All 7 checks | Pre-production gate |
| `post-deploy` | 5 checks (no bias/robustness) | Production monitoring |

---

## Live Dashboard

Running `raiflow check` (without `--no-dashboard`) opens a browser dashboard at `http://127.0.0.1:8000/`:

- Select pipeline stage and regulatory framework
- Click **Run Checks** to trigger a live run
- Watch results stream in real-time via SSE
- Per-article cards with pass/fail badges, scores, and remediation hints
- Click any card for detailed regulatory context (article citation, what's being tested)
- Overall compliance score and risk level (Low / Medium / High / Critical)
- **Download Report** button exports `raiflow-report-<timestamp>.json`

In CI environments (`CI=true` or no TTY), the dashboard is automatically suppressed.

---

## raiflow.yaml

`raiflow init` generates this for you. Edit it to match your system:

```yaml
system_name: "my-rag-app"
risk_level: "high"
compliance_framework: "eu_ai_act"

model_metadata:
  name: "llama3"
  disclosure_flag: true   # Article 13: users must know they're interacting with AI

risk_management:
  assessment_path: "docs/risk_assessment.md"   # Article 9

oversight:
  override_endpoints:
    - "/api/override"    # Article 14: human intervention endpoints
    - "/api/halt"

logging:
  middleware_active: true   # Article 12

data_governance:
  dataset_path: "data/training.csv"
  protected_attributes: ["gender", "ethnicity"]   # Article 10: bias detection

robustness:
  red_team_prompts_path: "tests/red_team.txt"   # Article 10: toxicity testing
  toxicity_threshold: 0.7
```

---

## GitHub Actions Integration

`raiflow init` drops a ready-to-use workflow into `.github/workflows/rai-compliance.yml`:

```yaml
# Runs on every PR targeting main
# Four jobs: pre-commit-checks → compliance-gate → build-and-sign → deploy-gate
# Blocks merge on compliance failure
# Produces signed artifact manifest with SHA-256 of compliance report
```

Set `COMPLIANCE_NOTIFY_EMAIL` as a repository secret to receive failure notifications.

---

## CLI Reference

```bash
raiflow init [--force] [--directory PATH]
    Scan project, generate raiflow.yaml and GitHub Actions workflow.
    --force     Overwrite existing files
    --directory Scan a different directory (default: current)

raiflow check [--stage STAGE] [--no-dashboard] [--dashboard] [--dry-run]
              [--manifest PATH] [--output PATH] [--threshold FLOAT]
              [--enable-llm-checks] [--dashboard-port INT]
    Run compliance checks for the specified pipeline stage.
    --stage         pre-commit | ci | pre-deploy | post-deploy (default: ci)
    --no-dashboard  Headless mode, terminal output only
    --dry-run       Run all checks but always exit 0
    --enable-llm-checks  Enable semantic LLM-based evaluators (requires Ollama or API key)

raiflow generate-tests [--policy PATH] [--output-dir PATH]
    Generate pytest compliance test files from policy YAML.
```

---

## Supported Frameworks

| Framework | Status |
|---|---|
| EU AI Act (2024/1689) | ✅ Active |
| NIST AI RMF 1.0 | 🔜 Coming soon |
| ISO/IEC 42001 | 🔜 Coming soon |

---

## Project Structure

```
raiflow/
├── cli.py              # Click CLI entry point
├── gate.py             # CheckRunner — static compliance checks
├── manifest.py         # raiflow.yaml Pydantic loader
├── dashboard_server.py # FastAPI server + SSE streaming
├── scanner.py          # AI framework detection
├── scaffolder.py       # raiflow.yaml + workflow generation
├── reporter.py         # JSON compliance report builder
├── generator.py        # pytest file generator
├── evaluators/         # EU AI Act evaluators (Articles 9–14)
├── dashboard/          # Single-file SPA (index.html)
└── data/               # Bundled policy YAML + workflow template
```

---

## Contributing

See [CONTRIBUTIONS.md](CONTRIBUTIONS.md). Issues and PRs welcome.

## License

MIT — see [LICENSE](LICENSE) for details.

---

*RaiFlow is a compliance assistance tool and does not constitute legal advice. Always consult qualified legal counsel for regulatory compliance matters.*
