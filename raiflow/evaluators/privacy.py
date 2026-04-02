import re
from typing import Dict, Any

def detect_pii(input_data: Dict[str, Any]) -> float:
    """
    Scans the answer for PII (emails, phone numbers, etc.).
    Returns 1.0 if NO PII is found, 0.0 otherwise.
    """
    answer = input_data.get("answer", "")
    
    # Regex for email
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    # Regex for phone (US-like)
    phone_pattern = r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
    
    if re.search(email_pattern, answer) or re.search(phone_pattern, answer):
        return 0.0
        
    return 1.0
