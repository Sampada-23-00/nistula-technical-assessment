"""
Single Claude call that returns both query classification and drafted reply.
Property context is injected into every prompt per the brief.
"""

import json
import logging

import anthropic

from app.models.schemas import QueryType

logger = logging.getLogger(__name__)

PROPERTY_CONTEXT = """\
Property: Villa B1, Assagao, North Goa
Bedrooms: 3 | Max guests: 6 | Private pool: Yes
Check-in: 2pm | Check-out: 11am
Base rate: INR 18,000 per night (up to 4 guests)
Extra guest: INR 2,000 per night per person
WiFi password: Nistula@2024
Caretaker: Available 8am to 10pm
Chef on call: Yes, pre-booking required
Availability April 20-24: Available
Cancellation: Free up to 7 days before check-in\
"""

_SYSTEM_PROMPT = f"""\
You are a warm, professional guest relations assistant for Nistula Villas.

{PROPERTY_CONTEXT}

For every guest message you must:
1. Classify it into EXACTLY one of these query types:
   - pre_sales_availability  (Is the villa available on these dates?)
   - pre_sales_pricing       (What is the rate for N adults / N nights?)
   - post_sales_checkin      (Check-in time, WiFi password, arrival info)
   - special_request         (Early check-in, airport transfer, dietary needs)
   - complaint               (Something is wrong, guest is unhappy)
   - general_enquiry         (Pets allowed? Parking? Other general questions)

2. Draft a helpful, warm reply that directly answers the guest's question using the\
 property context above. Address the guest by first name. Keep it concise (3–5 sentences).

Respond ONLY with a valid JSON object — no markdown, no extra text:
{{"query_type": "<one of the six types>", "reply": "<your drafted reply>"}}
"""


async def classify_and_reply(
    client: anthropic.AsyncAnthropic,
    model: str,
    guest_name: str,
    message: str,
) -> tuple[QueryType, str]:
    user_content = f"Guest: {guest_name}\nMessage: {message}"

    logger.debug("Sending message to Claude | guest=%s", guest_name)

    response = await client.messages.create(
        model=model,
        max_tokens=1024,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )

    raw = response.content[0].text.strip()
    logger.debug("Claude raw response: %s", raw)

    data = json.loads(raw)
    query_type: QueryType = data["query_type"]
    reply: str = data["reply"]

    return query_type, reply
