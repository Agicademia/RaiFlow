import os
import json
import time
import functools
import datetime
from typing import Any, Dict, Callable, Optional
from raiflow.engine import DeJureComplianceEngine
from raiflow.evaluators.llm_judge import RaiFlowJudge
from raiflow.framework_registry import get_framework_registry, select_framework

class RaiFlowShield:
    def __init__(self, 
                 framework_id: str = "eu_ai_act", 
                 model: str = "gemma2:2b", 
                 api_key: Optional[str] = None,
                 log_path: str = "raiflow_audit_trail.json"):
        self.framework_id = framework_id
        self.log_path = log_path
        
        # Initialize the Judge
        self.judge = RaiFlowJudge(model=model, api_key=api_key)
        
        # Get framework information
        framework = select_framework(framework_id)
        
        # Path to policy YAML
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.policy_path = os.path.join(base_path, framework.policy_file)
        
        # Initialize the Engine
        self.engine = DeJureComplianceEngine(self.policy_path, self.judge)
        
        # Store framework info for logging
        self.framework_name = framework.name
        
    def log_audit(self, event_data: Dict[str, Any]):
        """Append an audit event to the JSON log."""
        events = []
        if os.path.exists(self.log_path):
            try:
                with open(self.log_path, "r") as f:
                    events = json.load(f)
            except Exception as e:
                print(f"[SHIELD] Failed to load log file: {e}")
                events = []
        
        events.append({
            "timestamp": datetime.datetime.now().isoformat(),
            **event_data
        })
        
        with open(self.log_path, "w") as f:
            json.dump(events, f, indent=2)

# Global cache to avoid re-initializing engines on every function call
_SHIELD_CACHE = {}

def shield(framework: str = "eu_ai_act", policy: Optional[str] = None, model: Optional[str] = None, max_retries: int = 1):
    """
    Decorator for AI pipelines to automatically trigger compliance audits.
    
    Args:
        framework: Regulatory framework to use (alias for policy)
        policy: Regulatory framework to use (e.g., "eu_ai_act")
        model: LLM model to use for evaluation
        max_retries: Maximum retries for compliance evaluation
    """
    active_framework = policy or framework
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 1. Execute the actual RAG pipeline
            result = func(*args, **kwargs)
            
            # 2. Extract context and response for the audit
            source_text = ""
            if isinstance(result, dict):
                source_text = result.get("context", "")
                if not source_text:
                    source_text = result.get("answer", "")
            else:
                source_text = str(result)
            
            # 3. Get or Create Shield from cache
            api_key = os.getenv("GEMMA_API_KEY")
            active_model = model or ("gemma-4-31b-it" if api_key else "gemma2:2b")
            cache_key = f"{active_framework}_{active_model}"
            
            if cache_key not in _SHIELD_CACHE:
                print(f"[SHIELD] Initialized for {active_framework} via {active_model}")
                _SHIELD_CACHE[cache_key] = RaiFlowShield(
                    framework_id=active_framework, 
                    model=active_model, 
                    api_key=api_key
                )
            
            sh = _SHIELD_CACHE[cache_key]
            
            # Use smaller retry budget for middleware performance
            sh.engine.max_retries = max_retries 
            
            print(f"\n[SHIELD] Auditing {func.__name__} against {sh.framework_name}...")
            audit_report = sh.engine.run_compliance_audit(source_text)
            
            # 4. Log the results
            sh.log_audit({
                "function": func.__name__,
                "framework": sh.framework_id,
                "framework_name": sh.framework_name,
                "model": active_model,
                "audit_report": audit_report
            })
            
            return result
        return wrapper
    return decorator
