import logging
import uuid
from functools import lru_cache

import anthropic
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.models.schemas import (
    MessageResponse,
    NormalizedMessage,
    WebhookMessage,
)
from app.services.claude_service import classify_and_reply
from app.services.confidence import compute_confidence, determine_action

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    anthropic_api_key: str
    claude_model: str = "claude-sonnet-4-20250514"
    app_version: str = "1.0.0"

    # env_file_override_existing=True makes values from .env win over empty OS vars
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,   # treat empty OS env vars as unset → .env value wins
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


async def handle_webhook_message(payload: WebhookMessage) -> MessageResponse:
    settings = get_settings()
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    message_id = str(uuid.uuid4())
    logger.info(
        "Processing message | id=%s source=%s guest=%s",
        message_id,
        payload.source,
        payload.guest_name,
    )

    query_type, drafted_reply = await classify_and_reply(
        client=client,
        model=settings.claude_model,
        guest_name=payload.guest_name,
        message=payload.message,
    )

    normalized = NormalizedMessage(
        message_id=message_id,
        source=payload.source,
        guest_name=payload.guest_name,
        message_text=payload.message,
        timestamp=payload.timestamp,
        booking_ref=payload.booking_ref,
        property_id=payload.property_id,
        query_type=query_type,
    )

    confidence = compute_confidence(query_type, drafted_reply)
    action = determine_action(confidence, query_type)

    logger.info(
        "Result | id=%s query_type=%s confidence=%.4f action=%s",
        message_id,
        query_type,
        confidence,
        action,
    )

    return MessageResponse(
        message_id=normalized.message_id,
        query_type=query_type,
        drafted_reply=drafted_reply,
        confidence_score=confidence,
        action=action,
    )
