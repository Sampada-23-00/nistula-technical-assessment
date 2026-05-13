# Design Thinking — Nistula Guest Message Handler

## What this service does

Receives inbound guest messages from multiple sources (WhatsApp, Airbnb, Booking.com, Instagram, direct), normalises them into a unified schema, classifies the intent, drafts a property-aware reply via Claude, and returns a structured response with a confidence score and routing action — all in a single API call.

---

## Key design decisions

### 1. Single Claude call for both classification and reply

The brief implies two concerns (classify → reply), but separating them into two API calls would double latency and cost with no quality gain. Instead, the system prompt instructs Claude to return a JSON object with both `query_type` and `reply` in one shot. Claude's instruction-following is strong enough that this works reliably for 6 well-defined, non-overlapping categories.

**Trade-off:** A malformed JSON response from Claude would fail hard. Mitigated by tight system prompt constraints and a `json.loads` parse with error propagation.

### 2. Confidence is computed here, not by Claude

Asking a language model to self-report confidence yields poorly calibrated numbers — models tend to express high confidence even when uncertain. Instead, confidence is derived from two objective signals:

- **Query type** — pre-assigned base scores reflecting how much factual ground truth is available in the property context (checkin FAQ: 0.90, complaint: 0.45).
- **Reply content scan** — subtract 0.08 if the reply contains hedging language ("I'm not sure"), add up to 0.05 if it contains verifiable facts (exact rates, WiFi password).

This makes scoring transparent, deterministic, and operationally tunable without touching the model.

### 3. Complaints always escalate, regardless of confidence

A complaint with a "confident" auto-generated reply is still a complaint — it needs a human to acknowledge and own the resolution. Making this a hard rule (not a threshold) prevents a well-worded apology from slipping through as `auto_send`.

### 4. Property context is a prompt constant, not a database lookup

For a single-property MVP, embedding the context directly in the system prompt is the right call: zero latency, no infrastructure dependency, and the model can reason holistically over all facts at once. When Nistula scales to multiple properties, `PROPERTY_CONTEXT` becomes a lookup by `property_id`.

### 5. `lru_cache` on settings

`get_settings()` reads and validates the `.env` file once per process. Every subsequent call hits the cache. This avoids repeated disk I/O on hot paths without requiring a DI container.

---

## Action routing logic

| Condition | Action |
|---|---|
| `query_type == complaint` | `escalate` (hard rule, unconditional) |
| `confidence < 0.60` | `escalate` |
| `0.60 ≤ confidence ≤ 0.85` | `agent_review` |
| `confidence > 0.85` | `auto_send` |

Note: thresholds are `>` and `<`, not `>=` and `<=`, for clarity at boundary values.

---

## What I would add with more time

- **Multi-property support** — resolve property context by `property_id` from a config store or DB.
- **Retry with exponential backoff** — wrap the Anthropic call with `tenacity` for transient 529/503 errors.
- **Structured logging with request IDs** — propagate `message_id` through every log line for trace-level debugging.
- **Streaming reply** — stream Claude's output to reduce perceived latency on long replies.
- **Webhook signature verification** — validate HMAC signatures for Airbnb/Booking.com webhooks.
- **Rate limiting** — per-`source` throttle to prevent abuse.
- **Async DB persistence** — write `inbound_messages` + `message_responses` rows after responding, using `asyncpg`.
