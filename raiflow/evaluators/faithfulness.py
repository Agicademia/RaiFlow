import re
from typing import Dict, Any

def check_faithfulness(input_data: Dict[str, Any]) -> float:
    """
    Checks if the answer is grounded in the context.
    A simple word overlap score for demonstration.
    """
    context = input_data.get("context", "").lower()
    answer = input_data.get("answer", "").lower()
    
    if not context or not answer:
        return 0.0
        
    context_words = set(re.findall(r'\w+', context))
    answer_words = set(re.findall(r'\w+', answer))
    
    # Filter common stop words (simplified)
    stop_words = {'the', 'a', 'is', 'and', 'or', 'in', 'on', 'at', 'by', 'for', 'with', 'to', 'from'}
    answer_words = answer_words - stop_words
    
    if not answer_words:
        return 1.0
        
    overlap = answer_words.intersection(context_words)
    score = len(overlap) / len(answer_words)
    
    return score
