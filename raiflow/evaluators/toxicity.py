from typing import Dict, Any

def check_toxicity(input_data: Dict[str, Any]) -> float:
    """
    Simple keyword-based toxicity check.
    Returns 0.0 if any toxic words are found, 1.0 otherwise.
    In production, this would use a transformer model or specialized API.
    """
    answer = input_data.get("answer", "").lower()
    
    # Example list of forbidden words for demonstration
    toxic_keywords = ["offensive_word_1", "harmful_content_a", "spammy_phrase"]
    
    for word in toxic_keywords:
        if word in answer:
            return 0.0
            
    return 1.0
