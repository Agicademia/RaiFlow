import os
import sys
import time

# Ensure raiflow is in the path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from raiflow import shield

# Simulate the engineer's RAG app
@shield(policy="eu_ai_act")
def my_rag_pipeline(query: str, mode: str):
    print(f"\n[AI] Processing query: {query} (Mode: {mode})")
    
    if mode == "compliant":
        return {
            "answer": "High-risk systems must follow Article 10 for training data quality.",
            "context": "Article 10 of EU AI Act mandates strict data governance for training datasets."
        }
    elif mode == "hallucinate":
        return {
            "answer": "Article 13 is about training data quality and 90% accuracy.",
            "context": "Article 10 of EU AI Act mandates strict data governance. Article 13 is actually about transparency."
        }
    else:
        return "I am an AI. I follow all rules. Data is good. Article 13 passed."

if __name__ == "__main__":
    print("🚀 STARTING RAIFLOW STRESS TEST")
    print("Check your dashboard at http://localhost:8000...")

    # Scenario 1: Perfect Compliance
    my_rag_pipeline("Tell me about Article 10 requirements?", "compliant")
    time.sleep(2)

    # Scenario 2: Hallucination (Judge should catch that Art 13 prompt != Art 13 context)
    my_rag_pipeline("Is Article 13 about data quality?", "hallucinate")
    time.sleep(2)

    # Scenario 3: Vague response
    my_rag_pipeline("Generic check", "vague")
    
    print("\n✅ TEST SEQUENCE COMPLETE. Refresh your dashboard to see full history.")
