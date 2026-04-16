"""Interactive LLM setup wizard for raiflow.

Called by `raiflow init` and `raiflow check --enable-llm-checks` when no LLM
is configured. Guides the developer through choosing static-only or LLM-backed
checks, then sets up the chosen backend (API key or local Ollama model).
"""
from __future__ import annotations

import os
import subprocess
import sys
from typing import Optional

import click

# ── Supported backends ────────────────────────────────────────────────────────

API_MODELS = {
    "gemini-1.5-flash": {
        "label": "Google Gemini 1.5 Flash (fast, free tier available)",
        "env_var": "GEMMA_API_KEY",
        "key_url": "https://aistudio.google.com/app/apikey",
    },
    "gemini-1.5-pro": {
        "label": "Google Gemini 1.5 Pro (higher quality)",
        "env_var": "GEMMA_API_KEY",
        "key_url": "https://aistudio.google.com/app/apikey",
    },
    "gpt-4o-mini": {
        "label": "OpenAI GPT-4o Mini (requires OpenAI account)",
        "env_var": "OPENAI_API_KEY",
        "key_url": "https://platform.openai.com/api-keys",
    },
    "gpt-4o": {
        "label": "OpenAI GPT-4o (highest quality, higher cost)",
        "env_var": "OPENAI_API_KEY",
        "key_url": "https://platform.openai.com/api-keys",
    },
}

LOCAL_MODELS = {
    "gemma2:2b": "Google Gemma 2 2B — fast, low memory (~1.5 GB)",
    "gemma2:9b": "Google Gemma 2 9B — better quality (~5.5 GB)",
    "llama3.2:3b": "Meta Llama 3.2 3B — fast, good reasoning (~2 GB)",
    "mistral:7b": "Mistral 7B — strong compliance reasoning (~4.1 GB)",
}


# ── Public entry point ────────────────────────────────────────────────────────

def run_llm_setup_wizard() -> Optional[dict]:
    """Run the interactive LLM setup wizard.

    Returns a config dict with keys:
      - mode: "static" | "api" | "local"
      - model: model name (if LLM mode)
      - api_key: key value (if API mode) — caller should persist to env/yaml
      - env_var: env var name for the key (if API mode)

    Returns None if user chose static-only.
    """
    click.echo()
    click.echo("─" * 60)
    click.echo("  RaiFlow Evaluation Mode Setup")
    click.echo("─" * 60)
    click.echo()
    click.echo("  [1] Static checks only")
    click.echo("      Fast, no dependencies. Checks manifest fields,")
    click.echo("      file existence, and endpoint scanning.")
    click.echo()
    click.echo("  [2] Static + Semantic compliance checks (uses LLM)")
    click.echo("      Deeper analysis: transparency language, risk doc")
    click.echo("      quality, bias reasoning. Requires a model.")
    click.echo()

    choice = click.prompt("Choose evaluation mode", type=click.Choice(["1", "2"]), default="1")

    if choice == "1":
        click.echo("\n✓ Static-only mode selected.")
        return None

    # LLM mode — choose backend
    click.echo()
    click.echo("  [1] API key  (cloud model, no local install needed)")
    click.echo("  [2] Local model  (runs on your machine via Ollama)")
    click.echo()

    backend = click.prompt("Choose LLM backend", type=click.Choice(["1", "2"]), default="1")

    if backend == "1":
        return _setup_api_key()
    else:
        return _setup_local_model()


# ── API key setup ─────────────────────────────────────────────────────────────

def _setup_api_key() -> dict:
    click.echo()
    click.echo("Available API models:")
    click.echo()
    model_keys = list(API_MODELS.keys())
    for i, key in enumerate(model_keys, 1):
        click.echo(f"  [{i}] {API_MODELS[key]['label']}")
    click.echo()

    idx = click.prompt(
        "Choose model",
        type=click.IntRange(1, len(model_keys)),
        default=1,
    )
    model_id = model_keys[idx - 1]
    meta = API_MODELS[model_id]

    # Check if key already in environment
    existing_key = os.getenv(meta["env_var"])
    if existing_key:
        click.echo(f"\n✓ Found existing {meta['env_var']} in environment.")
        return {"mode": "api", "model": model_id, "api_key": existing_key, "env_var": meta["env_var"]}

    click.echo(f"\nGet your API key at: {meta['key_url']}")
    api_key = click.prompt(f"Paste your {meta['env_var']}", hide_input=True)

    if not api_key.strip():
        click.echo("No key provided — falling back to static-only mode.", err=True)
        return None

    click.echo(f"\n✓ {model_id} configured via API key.")
    return {"mode": "api", "model": model_id, "api_key": api_key.strip(), "env_var": meta["env_var"]}


# ── Local model setup ─────────────────────────────────────────────────────────

def _setup_local_model() -> dict:
    # Check Ollama is installed
    if not _ollama_available():
        click.echo()
        click.echo("Ollama is not installed or not on PATH.", err=True)
        click.echo("Install it from: https://ollama.com/download", err=True)
        click.echo("Then re-run: raiflow init", err=True)
        sys.exit(1)

    click.echo()
    click.echo("Available local models:")
    click.echo()
    model_keys = list(LOCAL_MODELS.keys())
    for i, key in enumerate(model_keys, 1):
        click.echo(f"  [{i}] {key} — {LOCAL_MODELS[key]}")
    click.echo()

    idx = click.prompt(
        "Choose model",
        type=click.IntRange(1, len(model_keys)),
        default=1,
    )
    model_id = model_keys[idx - 1]

    # Check if model already pulled
    if _model_exists_locally(model_id):
        click.echo(f"\n✓ {model_id} is already available locally.")
    else:
        click.echo(f"\nDownloading {model_id} via Ollama (this may take a few minutes)...")
        _pull_model(model_id)

    click.echo(f"\n✓ {model_id} ready for local inference.")
    return {"mode": "local", "model": model_id, "api_key": None, "env_var": None}


# ── Ollama helpers ────────────────────────────────────────────────────────────

def _ollama_available() -> bool:
    try:
        result = subprocess.run(
            ["ollama", "--version"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _model_exists_locally(model_id: str) -> bool:
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return model_id.split(":")[0] in result.stdout
    except Exception:
        return False


def _pull_model(model_id: str) -> None:
    try:
        subprocess.run(
            ["ollama", "pull", model_id],
            check=True,
        )
    except subprocess.CalledProcessError:
        click.echo(f"\nFailed to download {model_id}.", err=True)
        click.echo("Check your internet connection and try: ollama pull " + model_id, err=True)
        sys.exit(1)


# ── Config persistence helpers ────────────────────────────────────────────────

def apply_llm_config(config: dict) -> None:
    """Apply LLM config to the current process environment so gate.py picks it up."""
    if config is None:
        return
    if config.get("api_key") and config.get("env_var"):
        os.environ[config["env_var"]] = config["api_key"]
    if config.get("model"):
        os.environ["RAIFLOW_LLM_MODEL"] = config["model"]
    if config.get("mode"):
        os.environ["RAIFLOW_LLM_MODE"] = config["mode"]


def llm_configured() -> bool:
    """Return True if an LLM backend is already configured in the environment."""
    return bool(
        os.getenv("GEMMA_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("RAIFLOW_LLM_MODE") == "local"
    )
