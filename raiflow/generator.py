"""Test file generator — reads policy YAML and produces pytest compliance test files."""

import yaml
from pathlib import Path
from textwrap import dedent


class TestGenerator:
    """Generates pytest compliance test files from a policy YAML.

    One file per article section, plus special-case files for logging and bias.
    """

    def __init__(self, policy_path: str = "policies/eu_ai_act.yaml"):
        with open(policy_path) as f:
            self.policy = yaml.safe_load(f)

    def generate(self, output_dir: str) -> None:
        """Generate all test files into *output_dir*, creating it if needed."""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        for section in self.policy.get("regulatory_sections", []):
            self._write_article_file(section, out)
        self._write_logging_test(out)
        self._write_bias_test(out)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _article_slug(self, section: dict) -> str:
        """Return a filesystem-safe slug like ``article_9_risk_management``."""
        sid = section["section_id"]  # e.g. "Article 9"
        parts = sid.split()
        num = parts[1] if len(parts) > 1 else sid

        # Prefer the section title for the descriptive part; fall back to section_id
        title = section.get("title", sid)
        slug_part = title.lower().replace(" ", "_").replace("-", "_")
        return f"article_{num}_{slug_part}"

    def _write_article_file(self, section: dict, out: Path) -> None:
        sid = section["section_id"]  # e.g. "Article 9"
        slug = self._article_slug(section)
        rules = section.get("rules", [])

        lines = [
            f'"""Generated compliance tests for {sid} - DO NOT EDIT MANUALLY."""',
            "import pytest",
            "from raiflow.manifest import load_manifest",
            "",
        ]
        for rule in rules:
            rid = rule["rule_id"]
            label = rule.get("label", rid).replace('"', "'")
            fn_name = rid.lower().replace("-", "_")
            lines += [
                f"def test_{fn_name}():",
                f"    # {rid}: {label}",
                f"    m = load_manifest()",
                f"    # TODO: assert specific compliance condition for {rid}",
                f"    assert m is not None, 'Manifest must load for {rid}'",
                "",
            ]

        (out / f"test_{slug}.py").write_text("\n".join(lines), encoding="utf-8")

    def _write_logging_test(self, out: Path) -> None:
        (out / "test_logging_exists.py").write_text(
            dedent('''\
                """Generated: verify logging middleware is active (ART12-1)."""
                from raiflow.manifest import load_manifest

                def test_logging_middleware_active():
                    # ART12-1: Automatic Event Recording
                    m = load_manifest()
                    assert m.logging.middleware_active is True, (
                        "logging.middleware_active must be true in raiflow.yaml (Article 12)"
                    )
            '''),
            encoding="utf-8",
        )

    def _write_bias_test(self, out: Path) -> None:
        (out / "test_bias_metrics.py").write_text(
            dedent('''\
                """Generated: verify bias detection meets threshold (ART10-3)."""
                import yaml
                from raiflow.manifest import load_manifest
                from raiflow.evaluators.eu_ai_act import EUAIActEvaluators

                def test_bias_detection_threshold():
                    # ART10-3: Bias Detection and Mitigation
                    m = load_manifest()
                    if not m.data_governance.dataset_path:
                        import pytest; pytest.skip("No dataset_path declared in raiflow.yaml")
                    with open("policies/eu_ai_act.yaml") as f:
                        policy = yaml.safe_load(f)
                    art10 = next(s for s in policy["regulatory_sections"] if s["section_id"] == "Article 10")
                    rule = next(r for r in art10["rules"] if r["rule_id"] == "ART10-3")
                    threshold = rule.get("threshold", 0.90)
                    evals = EUAIActEvaluators()
                    data = {"context": str(m.data_governance.dataset_path), "answer": ""}
                    score = evals.bias_detection_check(data)
                    assert score >= threshold, f"Bias score {score:.2f} below threshold {threshold}"
            '''),
            encoding="utf-8",
        )
