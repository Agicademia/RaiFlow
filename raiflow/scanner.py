from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

# ── Framework classification ──────────────────────────────────────────────────

HIGH_RISK_FRAMEWORKS: List[str] = [
    "langchain", "openai", "ollama", "llama_index", "llama-index",
    "anthropic", "google.generativeai", "google-generativeai",
    "crewai", "autogen",
]

LIMITED_RISK_FRAMEWORKS: List[str] = [
    "transformers", "fastapi", "haystack", "semantic_kernel",
]

# Combined ordered list used for pattern matching
ALL_FRAMEWORKS: List[str] = HIGH_RISK_FRAMEWORKS + LIMITED_RISK_FRAMEWORKS

EXCLUDED_DIRS: set = {
    "__pycache__", ".venv", ".git", "node_modules", "site-packages",
}

# Regex: matches `import foo`, `import foo.bar`, `from foo import ...`
# Built once at module load from ALL_FRAMEWORKS.
_IMPORT_RE: re.Pattern = re.compile(
    r"^\s*(?:import|from)\s+("
    + "|".join(re.escape(f) for f in ALL_FRAMEWORKS)
    + r")\b",
    re.MULTILINE,
)


@dataclass
class DetectionResult:
    """Structured output of the Scanner."""
    frameworks: List[str] = field(default_factory=list)    # ordered, deduplicated
    risk_level: str = "minimal"                             # "high" | "limited" | "minimal"
    skipped_files: List[Path] = field(default_factory=list)


def scan_directory(root: Path) -> DetectionResult:
    """Walk *root* for .py files and detect AI framework imports.

    Excludes EXCLUDED_DIRS at every level of the tree.
    Skips unreadable files silently (PermissionError).
    Returns a DetectionResult with deduplicated frameworks and inferred risk_level.
    """
    import os

    seen: dict = {}  # framework -> first-seen order (preserves insertion order)
    skipped: List[Path] = []

    for dirpath, dirnames, filenames in os.walk(root):
        # Prune excluded dirs in-place so os.walk won't descend into them
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]

        for filename in filenames:
            if not filename.endswith(".py"):
                continue
            filepath = Path(dirpath) / filename
            try:
                content = filepath.read_text(encoding="utf-8", errors="replace")
            except PermissionError:
                skipped.append(filepath)
                continue

            for match in _IMPORT_RE.finditer(content):
                fw = match.group(1)
                if fw not in seen:
                    seen[fw] = len(seen)

    frameworks = sorted(seen.keys(), key=lambda f: seen[f])
    return DetectionResult(
        frameworks=frameworks,
        risk_level=infer_risk_level(frameworks),
        skipped_files=skipped,
    )


def infer_risk_level(frameworks: List[str]) -> str:
    """Return "high", "limited", or "minimal" based on detected frameworks.

    "high"    — at least one framework in HIGH_RISK_FRAMEWORKS
    "limited" — only frameworks in LIMITED_RISK_FRAMEWORKS (and at least one)
    "minimal" — no frameworks detected
    """
    if not frameworks:
        return "minimal"
    if any(f in HIGH_RISK_FRAMEWORKS for f in frameworks):
        return "high"
    return "limited"
