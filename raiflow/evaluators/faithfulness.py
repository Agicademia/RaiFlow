import re
from typing import Dict, Any


_STOP_WORDS = {
    'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'and', 'or', 'but', 'in', 'on', 'at', 'by', 'for', 'with', 'to',
    'from', 'of', 'that', 'this', 'it', 'its', 'as', 'not', 'no', 'so',
    'if', 'then', 'than', 'when', 'where', 'which', 'who', 'what', 'how',
    'we', 'our', 'you', 'your', 'they', 'their', 'he', 'she', 'his', 'her',
    'i', 'my', 'me', 'us', 'do', 'does', 'did', 'will', 'would', 'can',
    'could', 'should', 'may', 'might', 'must', 'shall', 'have', 'has', 'had',
}


def check_faithfulness(input_data: Dict[str, Any]) -> float:
    """
    Checks if the answer is grounded in the context using token overlap.

    Scores:
      1.0 = all answer tokens found in context (fully faithful)
      0.0 = no answer tokens found in context (hallucination)

    For production use, replace with an LLM-based judge (see llm_judge.py).
    """
    context = input_data.get("context", "").lower()
    answer = input_data.get("answer", "").lower()

    if not context or not answer:
        return 0.0

    context_words = set(re.findall(r'\b\w+\b', context)) - _STOP_WORDS
    answer_words = set(re.findall(r'\b\w+\b', answer)) - _STOP_WORDS

    if not answer_words:
        return 1.0  # Empty answer after filtering — nothing to contradict

    overlap = answer_words & context_words
    score = len(overlap) / len(answer_words)

    return round(min(1.0, max(0.0, score)), 4)
