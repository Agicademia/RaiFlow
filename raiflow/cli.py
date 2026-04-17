"""Click CLI entry point for RaiFlow compliance gate.

Exposes:
  raiflow check          — run compliance checks for a pipeline stage
  raiflow generate-tests — generate pytest files from policy YAML
"""

import importlib.resources
import json
import os
import sys
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

import click

from raiflow.dashboard_server import DashboardServer
from raiflow.gate import CheckRunner
from raiflow.manifest import load_manifest
from raiflow.reporter import build_report, write_report
from raiflow.scanner import scan_directory
from raiflow.scaffolder import render_manifest, write_manifest, write_workflow, build_summary, print_summary
from raiflow.llm_setup import run_llm_setup_wizard, apply_llm_config, llm_configured


def _is_ci() -> bool:
    """Return True if running in a CI environment (no TTY or CI env var set)."""
    return bool(os.getenv("CI")) or not sys.stdout.isatty()


_DEFAULT_POLICY = "policies/eu_ai_act.yaml"

def _resolve_policy(policy: str) -> str:
    """If the user passed the default policy path and it doesn't exist on disk,
    fall back to the copy bundled inside the raiflow package."""
    if policy == _DEFAULT_POLICY and not Path(policy).exists():
        try:
            ref = importlib.resources.files("raiflow.data").joinpath("eu_ai_act.yaml")
            return str(ref)
        except Exception:
            pass
    return policy


@click.group()
def cli():
    """RaiFlow — EU AI Act compliance gate for CI/CD pipelines."""


@cli.command("check")
@click.option(
    "--stage",
    type=click.Choice(["pre-commit", "ci", "pre-deploy", "post-deploy"]),
    default=None,
    help="Pipeline stage to run checks for.",
)
@click.option("--manifest", default="raiflow.yaml", show_default=True, help="Path to raiflow.yaml.")
@click.option(
    "--policy",
    default=_DEFAULT_POLICY,
    show_default=True,
    help="Path to policy YAML file.",
)
@click.option(
    "--output",
    default="raiflow-report.json",
    show_default=True,
    help="Path to write the compliance report.",
)
@click.option("--target", multiple=True, help="Source file(s) to scan for oversight endpoints.")
@click.option("--threshold", type=float, default=None, help="Override per-rule pass threshold (0.0–1.0).")
@click.option("--enable-llm-checks", is_flag=True, default=False, help="Enable opt-in LLM-based evaluators.")
@click.option("--dry-run", is_flag=True, default=False, help="Run all checks but always exit 0.")
@click.option("--dashboard", is_flag=True, default=False, help="Stream results to a local browser dashboard.")
@click.option("--no-dashboard", is_flag=True, default=False, help="Disable the browser dashboard (headless mode).")
@click.option("--dashboard-port", type=int, default=8000, show_default=True, help="Port for the dashboard server.")
def check(stage, manifest, policy, output, target, threshold, enable_llm_checks, dry_run, dashboard, no_dashboard, dashboard_port):
    """Run compliance checks for the specified pipeline stage."""
    # Requirement 2.8: default to 'ci' with deprecation-style warning
    if stage is None:
        click.echo(
            "Warning: --stage not specified, defaulting to 'ci'. "
            "Specify --stage explicitly in future.",
            err=True,
        )
        stage = "ci"

    # Requirement 1.2: missing manifest exits non-zero with human-readable error
    try:
        m = load_manifest(manifest)
    except FileNotFoundError as e:
        click.echo(str(e), err=True)
        sys.exit(1)

    runner = CheckRunner(m, _resolve_policy(policy), threshold, enable_llm_checks, list(target))

    # If LLM checks requested but no backend configured, run setup wizard
    if enable_llm_checks and not llm_configured():
        click.echo("LLM checks requested but no model is configured.")
        llm_config = run_llm_setup_wizard()
        if llm_config:
            apply_llm_config(llm_config)
        else:
            enable_llm_checks = False
            click.echo("Continuing with static checks only.")
        runner = CheckRunner(m, _resolve_policy(policy), threshold, enable_llm_checks, list(target))

    # Determine whether to use the dashboard (Requirements 1.1–1.5)
    use_dashboard = not no_dashboard and not _is_ci()
    use_dashboard = use_dashboard or (dashboard and not _is_ci())

    # Warn when --dashboard is explicitly passed in a CI environment
    if dashboard and _is_ci():
        click.echo("--dashboard ignored in CI environment", err=True)

    if use_dashboard:
        # Browser-initiated run: start server, open browser, block in serve_forever()
        server = DashboardServer(port=dashboard_port)
        actual_port = server.start()
        if not server.wait_ready(timeout=5.0):
            click.echo("Dashboard server failed to start", err=True)
            sys.exit(1)
        try:
            webbrowser.open(f"http://127.0.0.1:{actual_port}/")
        except Exception as exc:
            click.echo(f"Warning: could not open browser: {exc}", err=True)
        server.serve_forever()
        sys.exit(0)

    # Headless / CLI-only path (--no-dashboard or CI environment)
    exit_code = 0
    try:
        results = runner.run(stage)

        report = build_report(stage, m, results, enable_llm_checks=enable_llm_checks)
        write_report(report, output)

        failed = [r for r in results if r.status == "fail"]
        if failed:
            _print_failure_table(failed, stage)
            _maybe_write_notify(failed)
            exit_code = 0 if dry_run else 1
        else:
            click.echo(f"✅  All checks passed ({len(results)} checks, stage={stage})")

    except Exception:
        raise

    sys.exit(exit_code)


@cli.command("generate-tests")
@click.option(
    "--policy",
    default=_DEFAULT_POLICY,
    show_default=True,
    help="Path to policy YAML file.",
)
@click.option(
    "--output-dir",
    default="tests/generated",
    show_default=True,
    help="Directory to write generated test files.",
)
def generate_tests(policy, output_dir):
    """Generate pytest compliance test files from a policy YAML."""
    from raiflow.generator import TestGenerator

    gen = TestGenerator(_resolve_policy(policy))
    gen.generate(output_dir)
    click.echo(f"✅  Test files written to {output_dir}/")


@cli.command("intercept")
@click.option("--target", required=True, help="URL of the RAG app to proxy, e.g. http://localhost:7860")
@click.option("--port", type=int, default=8080, show_default=True, help="Port for the interceptor proxy.")
@click.option(
    "--framework",
    default="eu_ai_act",
    show_default=True,
    type=click.Choice(["eu_ai_act", "nist_ai_rmf"]),
    help="Compliance framework to audit against.",
)
@click.option("--log", "log_path", default="raiflow_audit_trail.json", show_default=True, help="Path to write the audit trail JSON.")
@click.option("--block-pii", is_flag=True, default=False, help="Block responses that contain PII (default: audit-only).")
def intercept(target, port, framework, log_path, block_pii):
    """Start a transparent HTTP proxy that audits every RAG API response in real-time.

    Point your client at http://localhost:PORT instead of the target app.
    Every request/response is checked for PII, toxicity, and faithfulness.
    Results are streamed to the terminal and appended to the audit trail log.

    \b
    Examples:
      raiflow intercept --target http://localhost:7860
      raiflow intercept --target http://localhost:7860 --port 9090 --block-pii
      raiflow intercept --target http://localhost:7860 --log audit.json
    """
    from raiflow.interceptor import run_interceptor
    run_interceptor(
        target=target,
        port=port,
        framework=framework,
        log_path=log_path,
        block_on_pii=block_pii,
    )


@cli.command("init")
@click.option("--force", is_flag=True, default=False, help="Overwrite existing raiflow.yaml and rai-compliance.yml.")
@click.option("--directory", default=".", show_default=True, help="Root directory to scan and write files into.")
def init(force: bool, directory: str) -> None:
    """Scaffold raiflow.yaml and .github/workflows/rai-compliance.yml for this project."""
    root = Path(directory)

    if not root.exists():
        click.echo(f"Directory not found: {directory}", err=True)
        sys.exit(1)

    if not root.is_dir():
        click.echo(f"Not a directory: {directory}", err=True)
        sys.exit(1)

    # Interactive LLM setup wizard
    llm_config = run_llm_setup_wizard()
    if llm_config:
        apply_llm_config(llm_config)

    detection = scan_directory(root)
    manifest_content = render_manifest(detection, system_name=root.resolve().name)
    manifest_result = write_manifest(manifest_content, root, force)
    workflow_result = write_workflow(root, force)
    summary = build_summary(detection, [manifest_result, workflow_result])
    print_summary(summary)

    if llm_config:
        click.echo(f"LLM checks: enabled ({llm_config['model']})")
        click.echo("Next step: raiflow check --stage ci --enable-llm-checks")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _print_failure_table(failed, stage):
    """Print a structured failure summary to stdout (Requirements 6.2, 6.3)."""
    click.echo(f"\n❌  {len(failed)} check(s) failed (stage={stage}):\n")
    for r in failed:
        click.echo(f"  [{r.article_id}] {r.rule_id} — {r.check_name}")
        click.echo(f"    Score: {r.score:.2f}  Threshold: {r.threshold:.2f}")
        click.echo(f"    Fix:   {r.remediation_hint}\n")


def _maybe_write_notify(failed):
    """Write raiflow-notify.json when COMPLIANCE_NOTIFY_EMAIL is set (Requirement 6.5)."""
    email = os.getenv("COMPLIANCE_NOTIFY_EMAIL")
    if not email:
        return
    payload = {
        "recipient": email,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "failures": [{"rule_id": r.rule_id, "hint": r.remediation_hint} for r in failed],
    }
    with open("raiflow-notify.json", "w") as f:
        json.dump(payload, f, indent=2)
