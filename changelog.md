# Changelog

All notable changes to the `raiflow` project will be documented in this file.

## [1.0.0] - 2026-04-16
### Added
- **RaiFlow HTTP Interceptor**: Launched terms-of-use-compliant proxy for transparent auditing of any RAG API endpoint.
- **De Jure Self-Repair Engine**: Iterative LLM-as-a-judge loop for high-fidelity compliance audits.
- **Project Analyzer**: Static analysis tool to scan projects for AI components and map regulatory risks.
- **EU AI Act Expansion**: 27 specialized evaluators covering Articles 9-14 (full technical documentation and human oversight support).
- **Control Plane UI**: Interactive dashboard for real-time audit trail visualization and reporting.
- **De Jure Ingestor**: Autonomous tool to convert official PDF legalese into RaiFlow YAML policies using Gemini Flash.
- **Standardized Audit Trail**: Article 12 compliant JSON record-keeping for all audit events.

### Changed
- **Evaluation Engine**: Moved from regex-based pilot checks to semantic LLM-based reasoning (Ollama/Gemini).
- **Policy Schema**: Upgraded YAML structure to support hierarchical definitions and conditions.

### Fixed
- Improved PII detection accuracy by integrating larger entity lists.
- Resolved token limit edge cases in the De Jure extraction loop.

---

## [0.1.0] - 2026-04-02
### Added
- Core `ComplianceEngine` for mapping policy IDs to technical checks.
- Initial policy mapping for **NIST AI RMF 1.0**.
- Evaluators for:
    - **Faithfulness** (Word-overlap based)
    - **PII Detection** (Regex-based)
    - **Toxicity** (Keyword-based)
- Standalone **Jupyter Notebook** version (`raiflow_compliance_walkthrough.ipynb`).
- **CI/CD pipeline** via GitHub Actions.
- Comprehensive `README.md` and enhancement roadmap.

---
*Note: This version is the pilot release for Agicademia venture studio.*
