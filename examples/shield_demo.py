import os
import sys
import time

# Ensure raiflow is in the path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from raiflow import shield

# Mock of a real-world RAG pipeline
@shield(framework="eu_ai_act")
def enterprise_rag_app(query: str):
    print(f"\n[APP] Processing query: '{query}'...")
    time.sleep(1) # Simulate RAG latency
    
    # Mock retrieved context and answer
    # In a real app, this would come from a Vector DB and LLM
    mock_response = {
        "answer": "High-risk AI systems must ensure data quality by following Article 10.",
        "context": "Article 10 of EU AI Act requires training data to be subject to appropriate data governance."
    }
    
    return mock_response

if __name__ == "__main__":
    print("--- RaiFlow Shield Middleware Demo ---")
    
    # Run the augmented pipeline
    result = enterprise_rag_app("What are the requirements for high-risk AI data?")
    
    print("\n" + "="*50)
    print("APP EXECUTION COMPLETE")
    print(f"Final Answer: {result['answer']}")
    print("="*50)
    
    if os.path.exists("raiflow_audit_trail.json"):
        print("\n[SUCCESS] Audit event captured in 'raiflow_audit_trail.json'")
    else:
        print("\n[ERROR] No audit trail found.")
