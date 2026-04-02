# raiflow: RAI Policy-to-Code Framework

`raiflow` is a technical framework designed to translate dense Responsible AI (RAI) policy documents (such as the **NIST AI RMF** or **EU AI Act**) into strict, testable Python assertions and automated CI/CD pipelines.

It provides a bridge between governance requirements and engineering enforcement for RAG (Retrieval-Augmented Generation) applications.

## 🚀 Key Features

- **Policy Mapping**: YAML-based schema linking governance IDs (e.g., `MEASURE-1.1`) to technical evaluators.
- **Compliance Engine**: A modular engine to run automated checks and generate compliance scores.
- **RAG-Specific Evaluators**:
    - **Faithfulness**: Verifies if answers are grounded in retrieved context (Faithfulness/Hallucination).
    - **PII Detection**: Automatically flags leakage of sensitive data (Emails, Phone numbers).
    - **Toxicity**: Keyword-based safety checks.
- **CI/CD Integrated**: Built-in support for GitHub Actions to enforce RAI compliance before deployment.
- **Jupyter Notebook Ready**: A single-file walkthrough for rapid experimentation.

## 📁 Project Structure

```text
raiflow/
├── evaluators/          # Specific compliance check logic
│   ├── faithfulness.py  # Hallucination/Grounding check
│   ├── privacy.py       # PII detection
│   └── toxicity.py      # Safety check
└── engine.py            # Core engine for mapping & running checks
policies/
└── nist_ai_rmf.yaml     # Policy mapping for NIST AI RMF 1.0
tests/
└── compliance_test.py   # Pytest suite for automated verification
.github/workflows/
└── rai-compliance.yml   # CI/CD pipeline configuration
rai_compliance_walkthrough.ipynb # Complete project in a single notebook
```

## 🛠️ Installation

1. **Clone the repository**:
   ```bash
   git clone <repo-url>
   cd "Frameworks to CICD"
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## 📖 Usage

### 1. Running Modular Compliance Tests
To run the compliance suite locally using `pytest`:
```bash
python -m pytest tests/compliance_test.py
```

### 2. Using the Jupyter Notebook
Open `rai_compliance_walkthrough.ipynb` in VS Code or Jupyter. 
> [!TIP]
> Run the first cell (`%pip install PyYAML ...`) to ensure all dependencies are correctly loaded in your kernel.

### 3. CI/CD Integration
The project includes a GitHub Action in `.github/workflows/rai-compliance.yml`. Simply push to `main` or create a PR to trigger the automated compliance checks.

## 💡 Future Enhancements

We are moving towards:
- **LLM-as-a-Judge**: Integrating `ragas` and `deepeval` for semantic evaluations.
- **Regulation Expansion**: Mapping the **EU AI Act** and **ISO 42001**.
- **Real-time Guardrails**: FastAPI/LangChain middleware for active protection.

For more details, see [enhancements_ideas.md](enhancements_ideas.md).

## ⚖️ License
MIT
