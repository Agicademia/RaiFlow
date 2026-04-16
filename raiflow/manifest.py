"""Pydantic schema and loader for raiflow.yaml compliance manifest."""

from __future__ import annotations

import warnings
from typing import List, Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field


class ModelMetadata(BaseModel):
    name: str
    version: str = ""
    disclosure_flag: bool


class RiskManagement(BaseModel):
    assessment_path: Optional[str] = None


class Oversight(BaseModel):
    override_endpoints: List[str] = Field(default_factory=list)


class Logging(BaseModel):
    middleware_active: bool


class DataGovernance(BaseModel):
    dataset_path: Optional[str] = None
    format: Optional[str] = None
    protected_attributes: List[str] = Field(default_factory=list)


class Robustness(BaseModel):
    red_team_prompts_path: Optional[str] = None
    toxicity_threshold: float = 0.7


class RaiFlowManifest(BaseModel):
    model_config = ConfigDict(extra="allow")

    system_name: str
    risk_level: str
    compliance_framework: str = "eu_ai_act"  # eu_ai_act | nist_ai_rmf | iso_42001
    eu_ai_act_articles: List[str] = Field(default_factory=list)
    model_metadata: ModelMetadata
    risk_management: RiskManagement = Field(default_factory=RiskManagement)
    oversight: Oversight = Field(default_factory=Oversight)
    logging: Logging
    data_governance: DataGovernance = Field(default_factory=DataGovernance)
    robustness: Robustness = Field(default_factory=Robustness)
    banned_models: List[str] = Field(default_factory=list)


def load_manifest(path: str = "raiflow.yaml") -> RaiFlowManifest:
    """Load and validate raiflow.yaml.

    Raises FileNotFoundError if the file is absent.
    Emits warnings.warn for any unrecognised top-level keys.
    """
    from pathlib import Path

    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(
            f"Compliance manifest not found: '{path}'\n"
            f"Hint: cp raiflow.yaml.example raiflow.yaml  and fill in your system details."
        )
    with open(p) as f:
        raw = yaml.safe_load(f) or {}

    known = set(RaiFlowManifest.model_fields.keys())
    for key in raw:
        if key not in known:
            warnings.warn(
                f"raiflow.yaml: unrecognised field '{key}' — ignored",
                stacklevel=2,
            )

    return RaiFlowManifest(**raw)
