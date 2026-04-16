import os
import requests
import json
import re
from typing import Dict, Any, List


class RaiFlowJudge:
    def __init__(self, model: str = "gemma2:2b", api_key: str = None, base_url: str = None):
        self.model = model
        self.api_key = api_key or os.getenv("GEMMA_API_KEY")

        # Determine endpoint based on API key presence
        if self.api_key:
            self.base_url = base_url or "https://generativelanguage.googleapis.com/v1beta/models/"
        else:
            self.base_url = f"{base_url or 'http://localhost:11434'}/api/generate"

    def _query_model(self, prompt: str) -> str:
        if self.api_key:
            return self._query_cloud(prompt)
        return self._query_local(prompt)

    def _query_local(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False
        }
        try:
            response = requests.post(self.base_url, json=payload, timeout=120)
            response.raise_for_status()
            return response.json().get("response", "")
        except Exception as e:
            print(f"Local Judge Error: {e}")
            return "ERROR: local fallback failed."

    def _query_cloud(self, prompt: str, max_network_retries: int = 2) -> str:
        """Query Gemma using System Instructions for maximum JSON adherence."""
        import time
        url = f"{self.base_url}{self.model}:generateContent?key={self.api_key}"
        
        system_instr = "You are a strict JSON-only regulatory compliance judge. Respond only with valid JSON. Never output prose or reasoning math."
        
        payload = {
            "system_instruction": {"parts": [{"text": system_instr}]},
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json"
            }
        }
        for attempt in range(max_network_retries + 1):
            try:
                response = requests.post(url, json=payload, timeout=300)
                response.raise_for_status()
                result = response.json()
                return result['candidates'][0]['content']['parts'][0]['text']
            except requests.exceptions.ConnectionError:
                if attempt < max_network_retries:
                    print(f"  [NET] Connection lost, retrying {attempt+1}/{max_network_retries}...")
                    time.sleep(5)
                    continue
                return ""
            except Exception as e:
                print(f"\n[API ERROR] {e}")
                return ""

    def evaluate_faithfulness(self, input_data: Dict[str, Any]) -> float:
        """Assess if the answer is grounded in the context."""
        context = input_data.get("context", "")
        answer = input_data.get("answer", "")

        prompt = f"""TASK: Evaluate if the Answer is logically grounded ONLY in the Context.
Score 1.0 = perfectly faithful, 0.0 = hallucination.

Context: {context}
Answer: {answer}

IMPORTANT: Reply with ONLY this JSON, no other text:
{{"score": 0.0, "reasoning": "your reasoning here"}}"""

        result = self._query_model(prompt)
        return self._extract_score(result)

    def evaluate_relevance(self, input_data: Dict[str, Any]) -> float:
        """Assess if the answer addresses the question."""
        question = input_data.get("question", "")
        answer = input_data.get("answer", "")

        prompt = f"""TASK: Evaluate if the Answer effectively addresses the Question.
Score 1.0 = perfectly relevant, 0.0 = irrelevant.

Question: {question}
Answer: {answer}

IMPORTANT: Reply with ONLY this JSON, no other text:
{{"score": 0.0, "reasoning": "your reasoning here"}}"""

        result = self._query_model(prompt)
        return self._extract_score(result)

    def judge_step(self, stage_name: str, input_text: str, extraction: Dict[str, Any], criteria: List[str]) -> Dict[str, Any]:
        """
        De Jure LLM-as-a-judge evaluation.
        Returns a score and a natural-language critique for targeted repair.
        """
        criteria_list = "\n".join([f'- "{c}": (score 0.0 to 1.0)' for c in criteria])
        extraction_str = json.dumps(extraction, indent=2)
        example_scores = ", ".join([f'"{c}": 0.75' for c in criteria[:2]])

        prompt = f"""You are a regulatory compliance judge. Score how well the extraction represents the source.
Use PARTIAL CREDIT - most extractions are partially correct, so scores between 0.4 and 0.9 are expected.
Only give 0.0 if the extraction is completely wrong or missing. Only give 1.0 if it is perfect.

STAGE: {stage_name}
SOURCE TEXT:
{input_text}

CURRENT EXTRACTION:
{extraction_str}

Score each criterion from 0.0 to 1.0 using partial credit:
{criteria_list}

Response must be a JSON object with this schema:
{{
  "average_score": float, 
  "critique": "string", 
  "per_criterion_scores": {{"criterion_name": float, ...}}
}}
"""

        raw_result = self._query_model(prompt)
        parsed = self._parse_judge_response(raw_result)

        # If per_criterion_scores exist, recompute average_score from them as a safety net
        pcs = parsed.get("per_criterion_scores", {})
        if pcs and len(pcs) > 0:
            try:
                computed_avg = sum(float(v) for v in pcs.values()) / len(pcs)
                # Use computed avg if the reported one looks fishy (exactly 0.0 with non-zero criteria)
                if parsed.get("average_score", 0.0) == 0.0 and computed_avg > 0.0:
                    parsed["average_score"] = round(computed_avg, 3)
            except Exception:
                pass

        return parsed

    def repair_extraction(self, stage_name: str, input_text: str, current_extraction: Dict[str, Any], critique: str) -> Dict[str, Any]:
        """
        The De Jure 'surgical repair' step.
        Takes the judge's critique and re-generates an improved extraction.
        """
        extraction_str = json.dumps(current_extraction, indent=2)

        prompt = f"""You are a regulatory data extraction expert. Improve the extraction based on the judge's critique.

STAGE: {stage_name}
SOURCE TEXT:
{input_text}

CURRENT EXTRACTION (to be improved):
{extraction_str}

JUDGE CRITIQUE (what needs to be fixed):
{critique}

Output the corrected JSON extraction object. Use the same schema as CURRENT EXTRACTION."""

        raw_result = self._query_model(prompt)

        # Try to parse the repaired extraction
        try:
            # Native JSON mode handles delimiters, but we strip fences just in case
            clean = re.sub(r'```(?:json)?\s*', '', raw_result).replace('```', '').strip()
            return json.loads(clean)
        except Exception:
            return current_extraction

        # If parsing fails, return original unchanged
        return current_extraction

    def _parse_judge_response(self, text: str) -> Dict[str, Any]:
        """Exhaustive extraction: JSON Mode -> raw_decode -> regex discovery."""
        if not text or "ERROR" in text:
            return {"average_score": 0.5, "critique": "API Error or Timeout.", "per_criterion_scores": {}}

        # 1. Clean and Try Direct Decode
        clean = re.sub(r'```(?:json)?\s*', '', text).replace('```', '').strip()
        try:
            return json.loads(clean)
        except Exception:
            pass

        # 2. Sequential Discovery (raw_decode)
        decoder = json.JSONDecoder()
        for i in range(len(clean)):
            if clean[i] == '{':
                try:
                    data, _ = decoder.raw_decode(clean[i:])
                    if isinstance(data, dict) and "average_score" in data:
                        return data
                except Exception:
                    continue

        # 3. Emergency Regex (Find any score/critique pattern in prose)
        score = 0.5
        critique = "Critique parsed from prose discovery."
        
        # Look for patterns like "Average: 0.95" or "Score: 0.75" or "average_score": 0.8
        s_match = re.search(r'(?:average_score|score|average|result)[\s"\':\*]*(\d+(?:\.\d+)?)', clean, re.IGNORECASE)
        if s_match:
            score = max(0.0, min(1.0, float(s_match.group(1))))
        
        c_match = re.search(r'(?:critique|feedback|comment)[\s"\':\*]+(.*?)(?:\n|$)', clean, re.IGNORECASE)
        if c_match:
            critique = c_match.group(1).strip()

        if score == 0.5:
            print(f"\n[PARSING FAILED] Falling back to 0.5. Raw content was:\n{text[:500]}...\n")

        return {"average_score": score, "critique": critique, "per_criterion_scores": {}}
        

    def _extract_score(self, text: str) -> float:
        """Extracts a numerical score from LLM JSON response."""
        try:
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return float(data.get("score", 0.0))
        except Exception:
            pass

        # Fallback regex
        match = re.search(r'score[:\s]+(\d+(?:\.\d+)?)', text)
        if match:
            return min(1.0, float(match.group(1)))

        return 0.5  # Neutral fallback
