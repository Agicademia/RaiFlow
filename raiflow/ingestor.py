import os
import yaml
import json
import requests
import time
from typing import List, Dict

class DeJureIngestor:
    """
    Implements Stage 2 of the De Jure paper: 
    Autonomous extraction of structured regulatory rules from local PDF text.
    """
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        # Using the absolute latest stable flash model
        self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={api_key}"

    def extract_rules(self, markdown_text: str, section_id: str) -> Dict:
        """
        Uses the specialized De Jure prompt with Gemma 4 (31B).
        """
        
        system_prompt = f"""You are an absolute expert legal annotator.
Your goal is to extract machine-readable JSON rules from the following text of the Official EU AI Act (2024/1689).
You MUST follow the De Jure schema.

## EXTRACTION RULES:
1. RULE_ID: Use format ART{{article_number}}-{{sequence}} (e.g. ART10-1).
2. ACTION: Extract the core legal obligation (e.g. "ensure", "monitor", "maintain").
3. TARGET: Identify who must comply (e.g. "Provider", "Deployer").
4. VERBATIM: Copy the exact sentence from the provided text.

YOU MUST RETURN ONLY A JSON OBJECT. NO PROSE.

Schema:
{{
  "section_id": "Article {section_id}",
  "metadata": {{ "citation": "Regulation (EU) 2024/1689", "title": "Article {section_id}" }},
  "rules": [
    {{
      "rule_id": "...",
      "label": "...",
      "type": "obligation",
      "action": "...",
      "target": "...",
      "conditions": "...",
      "verbatim": "..."
    }}
  ]
}}
"""

        payload = {
            "contents": [{"parts": [{"text": system_prompt + f"\n\nTEXT:\n{markdown_text}"}]}]
        }
        
        print(f"  > Querying Gemma 4 (31B) for {section_id}...")
        try:
            response = requests.post(self.api_url, json=payload, timeout=120)
            data = response.json()
            
            if 'error' in data:
                print(f"    [API Error] {data['error']['message']}")
                return None

            raw_output = data['candidates'][0]['content']['parts'][0]['text']
            
            # Robust JSON cleaning
            if "```json" in raw_output:
                raw_output = raw_output.split("```json")[1].split("```")[0].strip()
            elif "{" in raw_output:
                raw_output = "{" + raw_output.split("{", 1)[1].rsplit("}", 1)[0] + "}"
            
            parsed = json.loads(raw_output)
            print(f"    [OK] Extracted {len(parsed.get('rules', []))} rules.")
            return parsed
        except Exception as e:
            print(f"    [ERROR] Failed to parse response: {e}")
            return None

    def build_policy_yaml(self, raw_dir: str, output_path: str):
        full_policy = {
            "policy": "EU Artificial Intelligence Act",
            "version": "2024/1689",
            "regulatory_sections": []
        }
        
        # We only process the specific Official Article files we created from the PDF
        targets = ["article_10_official.md", "article_13_official.md"]
        
        for filename in targets:
            filepath = os.path.join(raw_dir, filename)
            if os.path.exists(filepath):
                section_num = filename.split("_")[1]
                
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                
                extracted = self.extract_rules(content, section_num)
                if extracted:
                    # Ensure definitions key exists for the engine
                    if "definitions" not in extracted:
                        extracted["definitions"] = []
                    full_policy["regulatory_sections"].append(extracted)
                
                # Small sleep for rate limits
                time.sleep(3)
        
        if len(full_policy["regulatory_sections"]) > 0:
            with open(output_path, "w", encoding="utf-8") as f:
                yaml.dump(full_policy, f, sort_keys=False)
            print(f"\n[SUCCESS] Authentic policy generated: {output_path}")
        else:
            print(f"\n[FATAL] Extraction failed for all sections. Check API logs.")

if __name__ == "__main__":
    api_key = os.getenv("GEMMA_API_KEY")
    if not api_key:
        print("[ERROR] GEMMA_API_KEY environment variable not set.")
    else:
        ingestor = DeJureIngestor(api_key)
        ingestor.build_policy_yaml("policies/raw", "policies/eu_ai_act_real.yaml")
