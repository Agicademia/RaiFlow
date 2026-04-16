#!/usr/bin/env python3
"""
Multi-Framework Compliance Demo

This script demonstrates how users can select different regulatory frameworks
for compliance checking with their AI applications.
"""

import os
import sys
import json
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from raiflow import (
    shield, 
    get_framework_registry, 
    select_framework, 
    list_available_frameworks
)
from raiflow.evaluators.llm_judge import RaiFlowJudge
from raiflow.framework_registry import FrameworkRegistry


def demo_framework_selection():
    """Demonstrate framework selection capabilities."""
    print("🏗️  RaiFlow Multi-Framework Compliance Demo")
    print("=" * 60)
    
    # List available frameworks
    print("\n📋 Available Regulatory Frameworks:")
    print("-" * 40)
    
    frameworks = list_available_frameworks()
    for fw in frameworks:
        print(f"\n  🏛️  {fw.id}")
        print(f"      Name: {fw.name}")
        print(f"      Description: {fw.description[:80]}...")
        print(f"      Jurisdiction: {fw.jurisdiction}")
        print(f"      Categories: {', '.join(fw.categories)}")
    
    print("\n" + "=" * 60)


def demo_shield_with_frameworks():
    """Demonstrate using shield decorator with different frameworks."""
    print("\n🛡️  Shield Decorator with Multiple Frameworks")
    print("-" * 60)
    
    # Example 1: EU AI Act compliance
    @shield(framework="eu_ai_act")
    def eu_compliant_rag(query: str):
        """RAG pipeline compliant with EU AI Act."""
        print(f"  🤖 Processing query: '{query}'")
        return {
            "answer": "Based on the retrieved documents...",
            "context": "Article 9 requires comprehensive risk management...",
            "sources": ["doc1", "doc2"]
        }
    
    # Example 2: NIST AI RMF compliance
    @shield(framework="nist_ai_rmf")
    def nist_compliant_rag(query: str):
        """RAG pipeline compliant with NIST AI RMF."""
        print(f"  🤖 Processing query: '{query}'")
        return {
            "answer": "Based on the analysis...",
            "context": "The system ensures faithfulness and relevance...",
            "sources": ["source1", "source2"]
        }
    
    # Test both pipelines
    print("\n🔍 Testing EU AI Act compliant pipeline:")
    eu_compliant_rag("What are the risk management requirements?")
    
    print("\n🔍 Testing NIST AI RMF compliant pipeline:")
    nist_compliant_rag("How do you ensure faithfulness?")
    
    print("\n✅ Both frameworks successfully applied!")


def demo_framework_registry():
    """Demonstrate direct use of framework registry."""
    print("\n📊 Framework Registry Direct Access")
    print("-" * 60)
    
    registry = get_framework_registry()
    
    # Get framework info
    eu_framework = registry.get_framework("eu_ai_act")
    print(f"\n📋 EU AI Act Framework:")
    print(f"   ID: {eu_framework.id}")
    print(f"   Name: {eu_framework.name}")
    print(f"   Policy File: {eu_framework.policy_file}")
    print(f"   Categories: {', '.join(eu_framework.categories)}")
    
    nist_framework = registry.get_framework("nist_ai_rmf")
    print(f"\n📋 NIST AI RMF Framework:")
    print(f"   ID: {nist_framework.id}")
    print(f"   Name: {nist_framework.name}")
    print(f"   Policy File: {nist_framework.policy_file}")
    print(f"   Categories: {', '.join(nist_framework.categories)}")
    
    # Get evaluators for a framework
    print("\n🔧 Getting evaluators for EU AI Act:")
    judge = RaiFlowJudge(model="llama3:latest")
    eu_evaluators = registry.get_evaluators("eu_ai_act", judge)
    all_evaluators = eu_evaluators.get_all_evaluators()
    print(f"   Available evaluators: {len(all_evaluators)}")
    for name in all_evaluators.keys():
        print(f"     - {name}")
    
    print("\n🔧 Getting evaluators for NIST AI RMF:")
    nist_evaluators = registry.get_evaluators("nist_ai_rmf", judge)
    nist_evals = nist_evaluators.get_all_evaluators()
    print(f"   Available evaluators: {len(nist_evals)}")
    for name in nist_evals.keys():
        print(f"     - {name}")


def demo_multi_framework_evaluation():
    """Demonstrate evaluating the same content against multiple frameworks."""
    print("\n🔄 Multi-Framework Evaluation")
    print("-" * 60)
    
    # Sample RAG output
    test_data = {
        "question": "How do you ensure your AI system is safe and compliant?",
        "context": """
        Our AI system implements comprehensive safety measures:
        - Risk management processes covering the entire lifecycle
        - Data governance with bias detection and mitigation
        - Technical documentation maintained and updated
        - Automatic logging for traceability
        - Transparent operation with clear explanations
        - Human oversight with intervention capabilities
        - Regular testing for faithfulness and relevance
        - Privacy protection and data security measures
        """,
        "answer": """
        We ensure safety and compliance through multiple layers:
        1. Comprehensive risk management and data governance
        2. Regular testing for accuracy, fairness, and reliability
        3. Transparent operations with human oversight
        4. Privacy protection and security measures
        5. Complete documentation and audit trails
        """
    }
    
    # Evaluate against both frameworks
    judge = RaiFlowJudge(model="llama3:latest")
    registry = get_framework_registry()
    
    print("\n📊 Evaluating against EU AI Act:")
    eu_results = registry.evaluate("eu_ai_act", judge, test_data)
    for check_name, score in eu_results.items():
        status = "✅" if score >= 0.5 else "❌"
        print(f"   {status} {check_name}: {score:.2f}")
    
    print("\n📊 Evaluating against NIST AI RMF:")
    nist_results = registry.evaluate("nist_ai_rmf", judge, test_data)
    for check_name, score in nist_results.items():
        status = "✅" if score >= 0.5 else "❌"
        print(f"   {status} {check_name}: {score:.2f}")


def main():
    """Run all demonstrations."""
    print("🚀 RaiFlow Multi-Framework Compliance Platform")
    print("=" * 60)
    
    try:
        # Demo 1: Framework selection
        demo_framework_selection()
        
        # Demo 2: Shield decorator
        demo_shield_with_frameworks()
        
        # Demo 3: Framework registry
        demo_framework_registry()
        
        # Demo 4: Multi-framework evaluation
        demo_multi_framework_evaluation()
        
        print("\n" + "=" * 60)
        print("✅ Multi-framework demonstration complete!")
        print("\n💡 Users can now select their preferred regulatory framework:")
        print("   - EU AI Act for European compliance")
        print("   - NIST AI RMF for US federal compliance")
        print("   - More frameworks can be added via the registry")
        
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())