from typing import Literal, Optional
from pydantic import BaseModel

Source = Literal["whatsapp", "booking_com", "airbnb", "instagram", "direct"]

QueryType = Literal[
    "pre_sales_availability",
    "pre_sales_pricing",
    "post_sales_checkin",
    "special_request",
    "complaint",
    "general_enquiry",
]

Action = Literal["auto_send", "agent_review", "escalate"]


class WebhookMessage(BaseModel):
    source: Source
    guest_name: str
    message: str
    timestamp: str
    booking_ref: Optional[str] = None
    property_id: Optional[str] = None


class NormalizedMessage(BaseModel):
    message_id: str
    source: Source
    guest_name: str
    message_text: str
    timestamp: str
    booking_ref: Optional[str] = None
    property_id: Optional[str] = None
    query_type: QueryType


class MessageResponse(BaseModel):
    message_id: str
    query_type: QueryType
    drafted_reply: str
    confidence_score: float
    action: Action
