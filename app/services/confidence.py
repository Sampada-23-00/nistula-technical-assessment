"""
Confidence scoring — never delegated to Claude.

Base scores per query type, then adjusted by reply content signals.
"""

from app.models.schemas import Action, QueryType

_BASE_SCORES: dict[QueryType, float] = {
    "post_sales_checkin":     0.90,
    "pre_sales_availability": 0.88,
    "pre_sales_pricing":      0.80,
    "special_request":        0.72,
    "general_enquiry":        0.65,
    "complaint":              0.45,
}

_UNCERTAIN_PHRASES = [
    "i'm not sure",
    "i am not sure",
    "not certain",
    "i don't know",
    "i do not know",
    "unclear",
    "i'm unable",
    "i cannot confirm",
    "may vary",
    "might be",
]

_FACTUAL_MARKERS = [
    "nistula@2024",       # WiFi password
    "inr 18,000",
    "inr 2,000",
    "2pm",
    "11am",
    "april 20",
    "available",
]


def compute_confidence(query_type: QueryType, reply: str) -> float:
    score = _BASE_SCORES[query_type]
    reply_lower = reply.lower()

    for phrase in _UNCERTAIN_PHRASES:
        if phrase in reply_lower:
            score -= 0.08
            break  # one penalty regardless of how many uncertain phrases appear

    factual_hits = sum(1 for marker in _FACTUAL_MARKERS if marker in reply_lower)
    if factual_hits >= 2:
        score += 0.05
    elif factual_hits == 1:
        score += 0.02

    return round(max(0.0, min(1.0, score)), 4)


def determine_action(confidence: float, query_type: QueryType) -> Action:
    if query_type == "complaint" or confidence < 0.60:
        return "escalate"
    if confidence > 0.85:
        return "auto_send"
    return "agent_review"
