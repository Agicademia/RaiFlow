#!/usr/bin/env python3
"""
Framework Registry for Multi-Framework Compliance Support

This module provides a registry pattern for managing multiple regulatory
frameworks and their evaluators, allowing users to select which framework
they want to use for compliance checking.
"""

from typing import Dict, Any, Optional, Type, Callable
from pathlib import Path
from dataclasses import dataclass

from raiflow.evaluators.llm_judge import RaiFlowJudge
from raiflow.evaluators.eu_ai_act import EUAIActEvaluators, create_eu_ai_act_evaluators
from raiflow.evaluators.nist_ai_rmf import NISTAIRMFEvaluators, create_nist_ai_rmf_evaluators


@dataclass
class FrameworkInfo:
    """Metadata about a regulatory framework."""
    id: str
    name: str
    description: str
    policy_file: str
    evaluator_class: Type
    create_function: Callable
    version: str = "1.0"
    jurisdiction: str = ""
    categories: list = None


class FrameworkRegistry:
    """Registry for managing multiple compliance frameworks."""
    
    def __init__(self):
        self._frameworks: Dict[str, FrameworkInfo] = {}
        self._evaluators_cache: Dict[str, Any] = {}
        self._register_builtin_frameworks()
    
    def _register_builtin_frameworks(self):
        """Register built-in regulatory frameworks."""
        
        # EU AI Act
        self.register(FrameworkInfo(
            id="eu_ai_act",
            name="EU Artificial Intelligence Act",
            description="Comprehensive EU regulation for AI systems covering risk management, data governance, transparency, and human oversight.",
            policy_file="policies/eu_ai_act.yaml",
            evaluator_class=EUAIActEvaluators,
            create_function=create_eu_ai_act_evaluators,
            version="1.0",
            jurisdiction="European Union",
            categories=["risk_management", "data_governance", "transparency", "human_oversight"]
        ))
        
        # NIST AI RMF
        self.register(FrameworkInfo(
            id="nist_ai_rmf",
            name="NIST AI Risk Management Framework",
            description="Framework for managing risks in AI systems focusing on validity, safety, security, and transparency.",
            policy_file="policies/nist_ai_rmf.yaml",
            evaluator_class=NISTAIRMFEvaluators,
            create_function=create_nist_ai_rmf_evaluators,
            version="1.0",
            jurisdiction="United States",
            categories=["faithfulness", "relevance", "safety", "privacy", "attribution"]
        ))
    
    def register(self, framework: FrameworkInfo):
        """Register a new compliance framework."""
        self._frameworks[framework.id] = framework
    
    def get_framework(self, framework_id: str) -> Optional[FrameworkInfo]:
        """Get framework information by ID."""
        return self._frameworks.get(framework_id)
    
    def list_frameworks(self) -> list:
        """List all available frameworks."""
        return list(self._frameworks.values())
    
    def get_evaluators(self, framework_id: str, judge: RaiFlowJudge) -> Any:
        """Get evaluators for a specific framework."""
        if framework_id not in self._frameworks:
            raise ValueError(f"Unknown framework: {framework_id}")
        
        # Check cache first
        cache_key = f"{framework_id}_{id(judge)}"
        if cache_key in self._evaluators_cache:
            return self._evaluators_cache[cache_key]
        
        # Create new evaluators
        framework = self._frameworks[framework_id]
        evaluators = framework.create_function(judge)
        
        # Cache and return
        self._evaluators_cache[cache_key] = evaluators
        return evaluators
    
    def get_policy_path(self, framework_id: str) -> Optional[str]:
        """Get the policy file path for a framework."""
        framework = self._frameworks.get(framework_id)
        if framework:
            return framework.policy_file
        return None
    
    def evaluate(self, framework_id: str, judge: RaiFlowJudge, data: Dict[str, Any]) -> Dict[str, float]:
        """Run all evaluators for a framework and return scores."""
        evaluators = self.get_evaluators(framework_id, judge)
        
        if hasattr(evaluators, 'get_all_evaluators'):
            all_evaluators = evaluators.get_all_evaluators()
        elif hasattr(evaluators, 'get_core_evaluators'):
            all_evaluators = evaluators.get_core_evaluators()
        else:
            raise ValueError(f"Evaluators for {framework_id} don't have get_all_evaluators method")
        
        results = {}
        for name, evaluator_func in all_evaluators.items():
            try:
                score = evaluator_func(data)
                results[name] = score
            except Exception as e:
                print(f"Warning: {name} evaluation failed: {e}")
                results[name] = 0.5
        
        return results


# Global registry instance
registry = FrameworkRegistry()


def get_framework_registry() -> FrameworkRegistry:
    """Get the global framework registry instance."""
    return registry


def select_framework(framework_id: str) -> FrameworkInfo:
    """Select a framework by ID."""
    framework = registry.get_framework(framework_id)
    if not framework:
        available = ", ".join(f.id for f in registry.list_frameworks())
        raise ValueError(f"Framework '{framework_id}' not found. Available: {available}")
    return framework


def list_available_frameworks() -> list:
    """List all available frameworks."""
    return registry.list_frameworks()