#!/usr/bin/env python3
"""
Enterprise RAG Pipeline with EU AI Act Compliance

This example demonstrates a realistic enterprise RAG pipeline with:
- Document ingestion and chunking
- Vector database storage
- Multi-stage retrieval and generation
- EU AI Act compliance monitoring
- Real-time compliance dashboard integration
"""

import os
import sys
import json
import time
import uuid
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from raiflow import shield
from raiflow.evaluators.eu_ai_act import EUAIActEvaluators
from raiflow.evaluators.llm_judge import RaiFlowJudge

@dataclass
class Document:
    """Represents a document in the knowledge base."""
    id: str
    title: str
    content: str
    source: str
    metadata: Dict[str, Any]

@dataclass
class RetrievalResult:
    """Represents a retrieved document chunk."""
    document_id: str
    content: str
    score: float
    metadata: Dict[str, Any]

class EnterpriseRAGPipeline:
    """Enterprise RAG pipeline with EU AI Act compliance monitoring."""
    
    def __init__(self):
        self.documents = []
        self.vector_store = {}
        self.compliance_monitor = None
        self.initialize_compliance_monitor()
        self.load_sample_documents()
    
    def initialize_compliance_monitor(self):
        """Initialize EU AI Act compliance monitoring."""
        try:
            judge = RaiFlowJudge(model="llama3:latest")
            self.compliance_monitor = EUAIActEvaluators(judge)
            print("✅ Compliance monitor initialized")
        except Exception as e:
            print(f"⚠️  Compliance monitor initialization failed: {e}")
            self.compliance_monitor = None
    
    def load_sample_documents(self):
        """Load sample documents for demonstration."""
        sample_docs = [
            Document(
                id="doc_001",
                title="EU AI Act Article 10 Compliance Guidelines",
                content="""
                Article 10 of the EU AI Act establishes requirements for data governance in high-risk AI systems.
                Training, validation, and testing data must be subject to appropriate data governance and management practices.
                Data sets must be relevant, representative, free of errors, and complete in view of the intended purpose.
                Providers must take into account the characteristics or elements that are particular to the specific geographical, behavioral, or functional setting.
                Special attention must be given to the use of sensitive data and the protection of personal data.
                """,
                source="EU Regulatory Guidelines",
                metadata={"category": "regulatory", "jurisdiction": "EU", "risk_level": "high"}
            ),
            Document(
                id="doc_002", 
                title="Risk Management Framework for AI Systems",
                content="""
                Risk management is a continuous, iterative process that shall include the following steps:
                1. Risk identification and analysis of the intended use and reasonably foreseeable misuse
                2. Risk estimation and evaluation based on the risk classification
                3. Risk evaluation against risk criteria
                4. Risk control measures implementation
                5. Residual risk assessment
                6. Risk management documentation
                The process must be documented and regularly updated throughout the system lifecycle.
                """,
                source="ISO 31000 Framework",
                metadata={"category": "risk_management", "standard": "ISO 31000", "risk_level": "medium"}
            ),
            Document(
                id="doc_003",
                title="Technical Documentation Requirements",
                content="""
                Technical documentation must contain comprehensive information about the AI system including:
                - System architecture and design specifications
                - Development process documentation
                - Testing and validation procedures
                - Risk management documentation
                - Data governance documentation
                - Performance metrics and accuracy assessments
                - Intended purpose and use cases
                - Limitations and known issues
                Documentation must be kept up-to-date and available for regulatory inspection.
                """,
                source="EU AI Act Article 11",
                metadata={"category": "documentation", "jurisdiction": "EU", "risk_level": "high"}
            ),
            Document(
                id="doc_004",
                title="Human Oversight Requirements",
                content="""
                High-risk AI systems must be designed and developed to ensure effective human oversight.
                This includes:
                - Human-machine interface tools for effective monitoring
                - Capability for human intervention at any stage
                - Clear indication of system confidence levels
                - Override mechanisms accessible to operators
                - Training materials for operators
                - Measures to prevent automation bias
                Human oversight must be proportionate to the risk and context of use.
                """,
                source="EU AI Act Article 14",
                metadata={"category": "human_oversight", "jurisdiction": "EU", "risk_level": "high"}
            )
        ]
        
        self.documents = sample_docs
        print(f"📚 Loaded {len(sample_docs)} sample documents")
    
    @shield(policy="eu_ai_act")
    def process_query(self, query: str, user_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Process a user query through the RAG pipeline with compliance monitoring.
        
        Args:
            query: User's natural language query
            user_context: Additional context about the user and use case
            
        Returns:
            Dictionary containing answer, sources, and compliance information
        """
        print(f"\n🔍 Processing query: '{query}'")
        
        # Step 1: Document Retrieval
        retrieved_docs = self.retrieve_documents(query)
        
        # Step 2: Context Generation
        context = self.generate_context(retrieved_docs)
        
        # Step 3: Answer Generation (simulated)
        answer = self.generate_answer(query, context)
        
        # Step 4: Compliance Assessment
        compliance_report = self.assess_compliance(query, context, answer, user_context)
        
        # Step 5: Response Assembly
        response = {
            "query": query,
            "answer": answer,
            "sources": [doc.document_id for doc in retrieved_docs],
            "confidence": max([doc.score for doc in retrieved_docs]) if retrieved_docs else 0.0,
            "compliance_report": compliance_report,
            "timestamp": datetime.now().isoformat(),
            "request_id": str(uuid.uuid4())
        }
        
        return response
    
    def retrieve_documents(self, query: str) -> List[RetrievalResult]:
        """Retrieve relevant documents using simple keyword matching."""
        print("  📋 Retrieving relevant documents...")
        time.sleep(0.5)  # Simulate retrieval latency
        
        results = []
        query_lower = query.lower()
        
        for doc in self.documents:
            # Simple relevance scoring based on keyword matching
            score = 0.0
            if any(keyword in doc.content.lower() for keyword in query_lower.split()):
                score = 0.7 + (len(query_lower.split()) * 0.05)
            
            if score > 0.5:  # Threshold for relevance
                results.append(RetrievalResult(
                    document_id=doc.id,
                    content=doc.content[:500],  # Truncate for context
                    score=min(score, 1.0),
                    metadata=doc.metadata
                ))
        
        # Sort by score
        results.sort(key=lambda x: x.score, reverse=True)
        print(f"  ✅ Retrieved {len(results)} relevant documents")
        return results
    
    def generate_context(self, retrieved_docs: List[RetrievalResult]) -> str:
        """Generate context from retrieved documents."""
        print("  🧠 Generating context...")
        time.sleep(0.3)  # Simulate context generation
        
        context_parts = []
        for doc in retrieved_docs:
            context_parts.append(f"Source {doc.document_id}: {doc.content}")
        
        return "\n\n".join(context_parts)
    
    def generate_answer(self, query: str, context: str) -> str:
        """Generate answer using the context (simulated LLM call)."""
        print("  🤖 Generating answer...")
        time.sleep(0.8)  # Simulate LLM generation latency
        
        # Simulate different types of answers based on query
        if "risk management" in query.lower():
            return """
            Based on the retrieved documents, here are the key requirements for risk management in AI systems:

            1. **Continuous Process**: Risk management must be continuous and iterative throughout the system lifecycle
            2. **Systematic Approach**: Include risk identification, analysis, estimation, evaluation, and control measures
            3. **Documentation**: Maintain comprehensive risk management documentation
            4. **Residual Risk**: Assess residual risks after implementing control measures
            5. **Regular Updates**: Update the risk management process as the system evolves

            The process should be proportionate to the risk level and context of use.
            """
        elif "data governance" in query.lower() or "article 10" in query.lower():
            return """
            Article 10 of the EU AI Act establishes comprehensive data governance requirements:

            1. **Data Quality**: Training, validation, and testing data must be relevant, representative, and free of errors
            2. **Data Management**: Implement appropriate data governance and management practices
            3. **Context Consideration**: Account for geographical, behavioral, and functional settings
            4. **Sensitive Data**: Special attention to sensitive data and personal data protection
            5. **Documentation**: Maintain records of data sources, processing, and quality assessments

            These requirements apply to high-risk AI systems and must be documented and auditable.
            """
        elif "technical documentation" in query.lower():
            return """
            Technical documentation requirements include:

            1. **System Architecture**: Complete system description and architecture documentation
            2. **Development Process**: Documentation of the development lifecycle and methodologies
            3. **Testing & Validation**: Comprehensive testing and validation procedures and results
            4. **Risk Management**: Documentation of risk assessments and mitigation measures
            5. **Data Governance**: Records of data sources, processing, and quality measures
            6. **Performance Metrics**: Accuracy assessments and performance evaluations
            7. **Limitations**: Known limitations and failure modes
            8. **Updates**: Version control and change management documentation

            Documentation must be kept current and available for regulatory inspection.
            """
        elif "human oversight" in query.lower():
            return """
            Human oversight requirements for high-risk AI systems:

            1. **Effective Monitoring**: Human-machine interface tools for continuous monitoring
            2. **Intervention Capability**: Ability for human intervention at any stage of operation
            3. **Clear Indication**: System must clearly indicate confidence levels and decision rationale
            4. **Override Mechanisms**: Accessible override mechanisms for operators
            5. **Training**: Comprehensive training materials for human operators
            6. **Automation Bias**: Measures to prevent automation bias and ensure human judgment
            7. **Proportionality**: Oversight measures must be proportionate to risk and context

            Human oversight ensures that AI systems remain under human control and accountability.
            """
        else:
            return f"""
            I found information related to your query about "{query}". 

            Based on the available documents, here's what I can tell you:

            [Note: This is a simulated response. In a real RAG system, this would be generated by an LLM based on the retrieved context.]

            For more specific information, please refine your query to focus on:
            - Risk Management
            - Data Governance (Article 10)
            - Technical Documentation
            - Human Oversight
            - EU AI Act compliance requirements
            """
    
    def assess_compliance(self, query: str, context: str, answer: str, user_context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Assess compliance with EU AI Act requirements."""
        print("  ⚖️  Assessing compliance...")
        
        if not self.compliance_monitor:
            return {"status": "monitor_unavailable", "message": "Compliance monitor not initialized"}
        
        # Prepare data for compliance assessment
        compliance_data = {
            "question": query,
            "context": context,
            "answer": answer
        }
        
        # Assess key compliance areas
        assessments = {}
        
        try:
            # Risk Management Assessment
            risk_score = self.compliance_monitor.risk_management_system_check(compliance_data)
            assessments["risk_management"] = {
                "score": risk_score,
                "status": "compliant" if risk_score >= 0.5 else "non_compliant",
                "requirement": "Article 9: Risk Management System"
            }
            
            # Data Governance Assessment
            data_score = self.compliance_monitor.data_governance_check(compliance_data)
            assessments["data_governance"] = {
                "score": data_score,
                "status": "compliant" if data_score >= 0.5 else "non_compliant",
                "requirement": "Article 10: Data Governance"
            }
            
            # Technical Documentation Assessment
            doc_score = self.compliance_monitor.technical_documentation_check(compliance_data)
            assessments["technical_documentation"] = {
                "score": doc_score,
                "status": "compliant" if doc_score >= 0.7 else "non_compliant",
                "requirement": "Article 11: Technical Documentation"
            }
            
            # Human Oversight Assessment
            oversight_score = self.compliance_monitor.human_oversight_design_check(compliance_data)
            assessments["human_oversight"] = {
                "score": oversight_score,
                "status": "compliant" if oversight_score >= 0.5 else "non_compliant",
                "requirement": "Article 14: Human Oversight"
            }
            
            # Calculate overall compliance
            scores = [assess["score"] for assess in assessments.values()]
            overall_score = sum(scores) / len(scores) if scores else 0.0
            
            compliance_report = {
                "overall_score": overall_score,
                "overall_status": "compliant" if overall_score >= 0.6 else "non_compliant",
                "assessments": assessments,
                "timestamp": datetime.now().isoformat(),
                "user_context": user_context or {}
            }
            
            print(f"  ✅ Compliance assessment complete (Overall: {overall_score:.2f})")
            return compliance_report
            
        except Exception as e:
            print(f"  ⚠️  Compliance assessment failed: {e}")
            return {
                "status": "assessment_failed",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

def main():
    """Demonstrate the enterprise RAG pipeline."""
    print("🚀 Enterprise RAG Pipeline with EU AI Act Compliance")
    print("=" * 60)
    
    # Initialize pipeline
    pipeline = EnterpriseRAGPipeline()
    
    # Sample queries to test different compliance areas
    test_queries = [
        "What are the requirements for risk management in AI systems?",
        "How should we handle data governance according to Article 10?",
        "What technical documentation is required for AI systems?",
        "What are the human oversight requirements for high-risk AI?",
        "How do we ensure compliance with the EU AI Act?"
    ]
    
    print(f"\n📋 Processing {len(test_queries)} test queries...\n")
    
    results = []
    for i, query in enumerate(test_queries, 1):
        print(f"\n{'='*20} Query {i} {'='*20}")
        
        # Process query with compliance monitoring
        result = pipeline.process_query(
            query=query,
            user_context={
                "user_id": f"user_{i:03d}",
                "department": "Compliance",
                "use_case": "Regulatory Research",
                "risk_level": "medium"
            }
        )
        
        results.append(result)
        
        # Display results
        print(f"\n📄 Answer: {result['answer'][:200]}...")
        print(f"📊 Compliance Score: {result['compliance_report'].get('overall_score', 0):.2f}")
        print(f"✅ Status: {result['compliance_report'].get('overall_status', 'unknown')}")
    
    # Summary
    print(f"\n{'='*60}")
    print("📊 COMPLIANCE SUMMARY")
    print("="*60)
    
    compliant_count = sum(1 for r in results if r['compliance_report'].get('overall_status') == 'compliant')
    avg_score = sum(r['compliance_report'].get('overall_score', 0) for r in results) / len(results)
    
    print(f"Total Queries: {len(results)}")
    print(f"Compliant Responses: {compliant_count}/{len(results)}")
    print(f"Average Compliance Score: {avg_score:.2f}")
    
    # Save results
    with open("enterprise_rag_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n💾 Results saved to 'enterprise_rag_results.json'")
    print("🎯 Pipeline demonstration complete!")

if __name__ == "__main__":
    main()