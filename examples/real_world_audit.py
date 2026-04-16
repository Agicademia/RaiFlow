import os
import sys
import time
import requests

# Path Fix
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from raiflow import shield

# The AI Model we are testing
# We'll use your Gemma 4 key to simulate a high-end RAG answer
API_KEY = "AIzaSyBUmFjjadYXFnCES29VcKdTxK9M48y2u40"
MODEL_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemma-4-31b-it:generateContent?key={API_KEY}"

@shield(policy="eu_ai_act_real")
def legal_qa_rag(query: str):
    print(f"\n[RAG] Analyzing: {query}")
    
    # Context: Our own codebase (raiflow/shield.py)
    # We want to see if the AI accurately evaluates our code against the law
    with open("raiflow/shield.py", "r") as f:
        code_context = f.read()
    
    prompt = f"""You are a legal compliance AI. 
Analyze the following code context and answer the user query.
Be specific about which EU AI Act rules are met.

CODE CONTEXT:
{code_context}

USER QUERY:
{query}
"""

    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        # Simulate a real LLM call for the RAG answer
        resp = requests.post(MODEL_URL, json=payload, timeout=60)
        answer = resp.json()['candidates'][0]['content']['parts'][0]['text']
        
        return {
            "answer": answer,
            "context": f"Applying EU AI Act 2024/1689 rules to RaiFlow Source Code. Context: {code_context[:200]}..."
        }
    except Exception as e:
        return f"RAG Error: {e}"

if __name__ == "__main__":
    print("--- STARTING AUTHENTIC REGULATORY AUDIT ---")
    print("Testing RaiFlow against the REAL EU AI Act (Extracted from PDF)...")
    
    # Test Query: Record Keeping (Article 12)
    # Background: Article 12 REQUIRES automatic logging for 6 months. 
    # Does our shield.py actually do that? (Spoiler: No, it just writes to a file).
    # If the AI says "Yes it's fully compliant", the Shield Judge should catch the LIE.
    
    result = legal_qa_rag("Is the RaiFlow Shield compliant with Article 12 requirements for automatic logging?")
    
    print("\n" + "="*50)
    print("RAG ANSWER:")
    print(result['answer'][:500] + "...")
    print("="*50)
    print("\n[SUCCESS] Audit sequence finished. check http://localhost:8000")
