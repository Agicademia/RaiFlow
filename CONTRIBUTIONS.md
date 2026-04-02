# Contributing to raiflow

First off, thank you for considering contributing to `raiflow`! It's people like you that make it a great tool for the Responsible AI community.

## How Can I Contribute?

### Reporting Bugs
- Use the GitHub Issues tab to report bugs.
- Include steps to reproduce and your environment details.

### Suggesting Enhancements
- If you have an idea for an enhancement, please open an issue first to discuss it.

### Pull Requests
1. Fork the repo and create your branch from `main`.
2. If you've added code that should be tested, add tests.
3. If you've changed APIs, update the documentation.
4. Ensure the test suite passes (`python -m pytest tests/compliance_test.py`).
5. Make sure your code follows the existing style.

## Development Setup

1. **Clone the repo**:
   ```bash
   git clone https://github.com/agicademia/raiflow.git
   cd raiflow
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows use `.venv\Scripts\activate`
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   pip install pytest  # for running tests
   ```

4. **Verify the installation**:
   ```bash
   python -m pytest tests/compliance_test.py
   ```

## Policy Governance
When contributing new policy mappings (e.g., EU AI Act), please follow the YAML schema defined in `policies/nist_ai_rmf.yaml`.

---
*By contributing, you agree that your contributions will be licensed under its MIT License.*
