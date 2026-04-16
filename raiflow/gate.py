"""CheckRunner — static compliance checks for the CI/CD gate.

All checks return a CheckResult and never raise unhandled exceptions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import importlib.resources
from pathlib import Path
from typing import Callable, List, Optional

from raiflow.engine import ComplianceEngine
from raiflow.evaluators.eu_ai_act import EUAIActEvaluators
from raiflow.evaluators.toxicity import check_toxicity
from raiflow.manifest import RaiFlowManifest


_DEFAULT_POLICY = "policies/eu_ai_act.yaml"


def _bundled_policy_path() -> str:
    """Return the path to the eu_ai_act.yaml bundled inside the raiflow package."""
    ref = importlib.resources.files("raiflow.data").joinpath("eu_ai_act.yaml")
    return str(ref)


def _resolve_policy(policy: str) -> str:
    """Fall back to the bundled policy when the default path doesn't exist on disk."""
    from pathlib import Path
    if policy == _DEFAULT_POLICY and not Path(policy).exists():
        return _bundled_policy_path()
    return policy


@dataclass
class CheckResult:
    article_id: str
    rule_id: str
    check_name: str
    status: str          # "pass" | "fail" | "skipped"
    score: float         # 0.0–1.0
    threshold: float
    remediation_hint: str = ""
    skip_reason: str = ""


class CheckRunner:
    def __init__(
        self,
        manifest: RaiFlowManifest,
        policy_path: str = _DEFAULT_POLICY,
        threshold_override: Optional[float] = None,
        enable_llm_checks: bool = False,
        target_files: List[str] = None,
    ):
        self.manifest = manifest
        self.threshold_override = threshold_override
        self.enable_llm_checks = enable_llm_checks
        self.target_files = target_files or []

        self.engine = ComplianceEngine(_resolve_policy(policy_path))

    # ------------------------------------------------------------------
    # Stage dispatch
    # ------------------------------------------------------------------

    def run(self, stage: str) -> List[CheckResult]:
        """Dispatch checks appropriate for the given stage."""
        results: List[CheckResult] = []

        # pre-commit: lightweight only
        results.append(self._check_banned_models())
        if stage == "pre-commit":
            return results

        # All other stages: full static checks
        results.append(self._check_transparency())
        results.append(self._check_risk_management())
        results.append(self._check_human_oversight())
        results.append(self._check_logging())

        # ci and pre-deploy also run bias + robustness
        if stage in ("ci", "pre-deploy"):
            results.append(self._check_bias_detection())
            results.append(self._check_robustness())

        return results

    def run_streaming(
        self,
        stage: str,
        on_result: Callable[[CheckResult], None],
    ) -> List[CheckResult]:
        """Run checks for stage, calling on_result after each one completes."""
        results: List[CheckResult] = []

        result = self._check_banned_models()
        on_result(result)
        results.append(result)
        if stage == "pre-commit":
            return results

        for check in (
            self._check_transparency,
            self._check_risk_management,
            self._check_human_oversight,
            self._check_logging,
        ):
            result = check()
            on_result(result)
            results.append(result)

        if stage in ("ci", "pre-deploy"):
            for check in (self._check_bias_detection, self._check_robustness):
                result = check()
                on_result(result)
                results.append(result)

        return results

    # ------------------------------------------------------------------
    # Static checks
    # ------------------------------------------------------------------

    def _check_transparency(self) -> CheckResult:
        """Article 13 — Transparency by Design (ART13-1)."""
        article_id = "Article 13"
        rule_id = "ART13-1"
        check_name = "Transparency by Design"
        threshold = 1.0

        if self.manifest.model_metadata.disclosure_flag is True:
            return CheckResult(
                article_id=article_id,
                rule_id=rule_id,
                check_name=check_name,
                status="pass",
                score=1.0,
                threshold=threshold,
            )
        return CheckResult(
            article_id=article_id,
            rule_id=rule_id,
            check_name=check_name,
            status="fail",
            score=0.0,
            threshold=threshold,
            remediation_hint="Set model_metadata.disclosure_flag: true in raiflow.yaml (Article 13)",
        )

    def _check_risk_management(self) -> CheckResult:
        """Article 9 — Risk Management Documentation (ART9-1)."""
        article_id = "Article 9"
        rule_id = "ART9-1"
        check_name = "Risk Management Documentation"
        threshold = 1.0
        remediation = (
            "Create a risk assessment document and set "
            "risk_management.assessment_path in raiflow.yaml"
        )

        assessment_path = self.manifest.risk_management.assessment_path
        if assessment_path is None:
            return CheckResult(
                article_id=article_id,
                rule_id=rule_id,
                check_name=check_name,
                status="fail",
                score=0.0,
                threshold=threshold,
                remediation_hint=remediation,
                skip_reason="missing_evidence",
            )

        if not Path(assessment_path).exists():
            return CheckResult(
                article_id=article_id,
                rule_id=rule_id,
                check_name=check_name,
                status="fail",
                score=0.0,
                threshold=threshold,
                remediation_hint=remediation,
                skip_reason="missing_evidence",
            )

        return CheckResult(
            article_id=article_id,
            rule_id=rule_id,
            check_name=check_name,
            status="pass",
            score=1.0,
            threshold=threshold,
        )

    def _check_human_oversight(self) -> CheckResult:
        """Article 14 — Human Oversight Endpoints (ART14-1)."""
        article_id = "Article 14"
        rule_id = "ART14-1"
        check_name = "Human Oversight Endpoints"
        threshold = 1.0

        if not self.target_files:
            return CheckResult(
                article_id=article_id,
                rule_id=rule_id,
                check_name=check_name,
                status="fail",
                score=0.0,
                threshold=threshold,
                remediation_hint=(
                    "Pass --target <source_file> to check endpoint definitions"
                ),
                skip_reason="missing_evidence",
            )

        # Read all target file contents
        file_contents: List[str] = []
        for fpath in self.target_files:
            try:
                file_contents.append(Path(fpath).read_text(encoding="utf-8", errors="replace"))
            except OSError:
                pass  # missing target file — endpoint won't be found

        endpoints = self.manifest.oversight.override_endpoints
        missing = [
            ep for ep in endpoints
            if not any(ep in content for content in file_contents)
        ]

        if not missing:
            return CheckResult(
                article_id=article_id,
                rule_id=rule_id,
                check_name=check_name,
                status="pass",
                score=1.0,
                threshold=threshold,
            )

        return CheckResult(
            article_id=article_id,
            rule_id=rule_id,
            check_name=check_name,
            status="fail",
            score=0.0,
            threshold=threshold,
            remediation_hint=(
                f"Missing oversight endpoints in target files: {', '.join(missing)}"
            ),
        )

    def _check_logging(self) -> CheckResult:
        """Article 12 — Logging Middleware Active (ART12-1)."""
        article_id = "Article 12"
        rule_id = "ART12-1"
        check_name = "Logging Middleware Active"
        threshold = 1.0

        if self.manifest.logging.middleware_active is True:
            return CheckResult(
                article_id=article_id,
                rule_id=rule_id,
                check_name=check_name,
                status="pass",
                score=1.0,
                threshold=threshold,
            )
        return CheckResult(
            article_id=article_id,
            rule_id=rule_id,
            check_name=check_name,
            status="fail",
            score=0.0,
            threshold=threshold,
            remediation_hint="Set logging.middleware_active: true in raiflow.yaml (Article 12)",
        )

    def _check_banned_models(self) -> CheckResult:
        """Banned Model Scan (BAN-1)."""
        article_id = "Banned Models"
        rule_id = "BAN-1"
        check_name = "Banned Model Scan"
        threshold = 1.0

        name = self.manifest.model_metadata.name
        if name not in self.manifest.banned_models:
            return CheckResult(
                article_id=article_id,
                rule_id=rule_id,
                check_name=check_name,
                status="pass",
                score=1.0,
                threshold=threshold,
            )
        return CheckResult(
            article_id=article_id,
            rule_id=rule_id,
            check_name=check_name,
            status="fail",
            score=0.0,
            threshold=threshold,
            remediation_hint=f"Remove or replace the banned model: {name}",
        )

    def _check_bias_detection(self) -> CheckResult:
        """Article 10 — Bias Detection (ART10-3)."""
        article_id = "Article 10"
        rule_id = "ART10-3"
        check_name = "Bias Detection"
        threshold = self.threshold_override if self.threshold_override is not None else 0.90

        dataset_path = self.manifest.data_governance.dataset_path
        if dataset_path is None:
            return CheckResult(
                article_id=article_id,
                rule_id=rule_id,
                check_name=check_name,
                status="skipped",
                score=0.0,
                threshold=threshold,
                skip_reason="no_dataset_declared",
            )

        protected_attributes = self.manifest.data_governance.protected_attributes

        try:
            evaluators = EUAIActEvaluators(enable_llm=self.enable_llm_checks)
            score = evaluators.bias_detection_check({
                "context": dataset_path,
                "answer": "",
                "protected_attributes": protected_attributes,
            })
        except Exception as exc:
            return CheckResult(
                article_id=article_id,
                rule_id=rule_id,
                check_name=check_name,
                status="fail",
                score=0.0,
                threshold=threshold,
                remediation_hint=f"Bias detection check failed: {exc}",
            )

        if score >= threshold:
            return CheckResult(
                article_id=article_id,
                rule_id=rule_id,
                check_name=check_name,
                status="pass",
                score=score,
                threshold=threshold,
            )
        return CheckResult(
            article_id=article_id,
            rule_id=rule_id,
            check_name=check_name,
            status="fail",
            score=score,
            threshold=threshold,
            remediation_hint=(
                f"Bias score {score:.2f} is below threshold {threshold:.2f}. "
                "Review dataset for biases affecting protected attributes."
            ),
        )

    def _check_robustness(self) -> CheckResult:
        """Article 10 — Robustness/Toxicity Check (ART10-4)."""
        article_id = "Article 10"
        rule_id = "ART10-4"
        check_name = "Robustness/Toxicity Check"
        tox_threshold = self.manifest.robustness.toxicity_threshold

        prompts_path = self.manifest.robustness.red_team_prompts_path
        if prompts_path is None:
            return CheckResult(
                article_id=article_id,
                rule_id=rule_id,
                check_name=check_name,
                status="skipped",
                score=0.0,
                threshold=tox_threshold,
                skip_reason="no_red_team_prompts",
            )

        try:
            prompts = Path(prompts_path).read_text(encoding="utf-8", errors="replace").splitlines()
            prompts = [p for p in prompts if p.strip()]
        except OSError:
            return CheckResult(
                article_id=article_id,
                rule_id=rule_id,
                check_name=check_name,
                status="fail",
                score=0.0,
                threshold=tox_threshold,
                skip_reason="missing_evidence",
                remediation_hint=f"Red team prompts file not found: {prompts_path}",
            )

        count_tested = len(prompts)
        failures = 0
        max_score = 0.0

        for prompt in prompts:
            try:
                # check_toxicity returns 1.0 = safe, 0.0 = toxic
                safety_score = check_toxicity({"answer": prompt})
                # Convert to toxicity score: 1.0 = fully toxic, 0.0 = safe
                toxicity_score = 1.0 - safety_score
                if toxicity_score > max_score:
                    max_score = toxicity_score
                # Fail if toxicity exceeds threshold
                if toxicity_score > tox_threshold:
                    failures += 1
            except Exception:
                failures += 1

        hint = (
            f"Tested {count_tested} prompts; {failures} failure(s); "
            f"max toxicity score: {max_score:.2f}"
        )

        if failures == 0:
            return CheckResult(
                article_id=article_id,
                rule_id=rule_id,
                check_name=check_name,
                status="pass",
                score=1.0 - max_score,
                threshold=tox_threshold,
                remediation_hint=hint,
            )
        return CheckResult(
            article_id=article_id,
            rule_id=rule_id,
            check_name=check_name,
            status="fail",
            score=1.0 - max_score,
            threshold=tox_threshold,
            remediation_hint=hint,
        )
