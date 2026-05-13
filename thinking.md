# Design Thinking — Nistula Guest Message Handler

---

## What this service does

Receives inbound guest messages from multiple sources (WhatsApp, Airbnb, Booking.com, Instagram, direct), normalises them into a unified schema, classifies the intent, drafts a property-aware reply via Claude, and returns a structured response with a confidence score and routing action — all in a single HTTP round-trip.

---

## Part 1 — API Design Decisions

### 1. Single Claude call for both classification and reply

The brief implies two concerns (classify → reply), but separating them into two API calls would double latency and cost with no quality gain. Instead, the system prompt instructs Claude to return a JSON object with both `query_type` and `reply` in one shot. Claude's instruction-following is strong enough that this works reliably for 6 well-defined, non-overlapping categories.

**Trade-off:** A malformed JSON response from Claude would fail hard. Mitigated by tight system prompt constraints and a `json.loads` parse with explicit error propagation to the caller.

### 2. Confidence is computed locally, never delegated to Claude

Asking a language model to self-report confidence yields poorly calibrated numbers — models tend to assert high confidence even when uncertain. Instead, confidence is derived from two deterministic signals:

- **Query type base score** — pre-assigned values reflecting how much verifiable ground truth exists in the property context (checkin FAQ: 0.90, complaint: 0.45, pricing: 0.80, etc.).
- **Reply content scan** — subtract 0.08 if the reply contains hedging language ("I'm not sure", "may vary"), add up to 0.05 if it contains verifiable facts (exact rates, WiFi password, confirmed availability).

This makes scoring transparent, auditable, and operationally tunable without touching the model or retraining anything.

### 3. Complaints always escalate regardless of confidence score

A complaint with a "confident" auto-generated reply is still a complaint — it needs a human to acknowledge and own the resolution. Making this a hard rule (not a threshold) prevents a well-worded apology from slipping through as `auto_send`. The same logic applies: the cost of missing a real guest crisis far outweighs the cost of an unnecessary escalation.

### 4. Property context is a prompt constant, not a database lookup

For a single-property MVP, embedding the context directly in the system prompt is the correct call: zero latency, no infrastructure dependency, and the model reasons holistically over all facts simultaneously. When Nistula scales to multiple properties, `PROPERTY_CONTEXT` becomes a per-request lookup by `property_id` from a config store or database.

### 5. `lru_cache` on settings

`get_settings()` reads and validates the `.env` file once per process lifetime. Every subsequent request hits the in-memory cache. This avoids repeated disk I/O on hot paths without introducing a dependency injection container.

### 6. `env_ignore_empty=True` in pydantic-settings

If `ANTHROPIC_API_KEY` is present in the OS environment as an empty string (common in CI or shared developer machines), pydantic-settings would silently use the empty value over the `.env` file. Setting `env_ignore_empty=True` ensures the `.env` file value wins whenever the OS variable is blank — the correct, expected behaviour for a secret.

---

## Action Routing Logic

| Condition | Action |
|---|---|
| `query_type == complaint` | `escalate` — hard rule, unconditional |
| `confidence < 0.60` | `escalate` |
| `0.60 ≤ confidence ≤ 0.85` | `agent_review` |
| `confidence > 0.85` | `auto_send` |

---

## Part 2 — Schema Design Decisions

### Why four tables instead of two

The initial schema covered `inbound_messages` and `message_responses` — enough for the API to function. But the assessment explicitly requires guest profiles, conversation grouping, reservation linkage, and reply lifecycle tracking. Four tables address this cleanly:

| Table | Purpose |
|---|---|
| `guests` | Unified guest identity across all channels — one row per person regardless of whether they contact via WhatsApp, Airbnb, or direct booking |
| `conversations` | Groups all messages under a single booking journey; links `guest_id` to `booking_ref` and `property_id` |
| `inbound_messages` | Every normalised inbound message, linked to its conversation |
| `message_responses` | AI output with full lifecycle tracking |

### reply_status — drafted / edited / auto_sent / agent_sent / escalated

This single column satisfies the "AI drafted vs edited vs auto-sent" requirement. The lifecycle is:

1. Row is inserted with `reply_status = 'drafted'` and `final_reply = NULL`.
2. If an agent edits before sending: `final_reply` is populated, `reply_status = 'edited'`.
3. On delivery: `reply_status` becomes `auto_sent`, `agent_sent`, or `escalated`; `sent_at` is stamped.

This gives operations a full audit trail without a separate event/audit table.

### Reservations linkage via `booking_ref`

Rather than creating a separate `reservations` table (which would require a booking management system to populate), `booking_ref` is stored as a plain text foreign key on both `conversations` and `inbound_messages`. This keeps the schema self-contained and lets it link to an external reservations system later without a schema migration.

### Indexing strategy

Indexes are placed on columns that appear in the most common operational queries:
- `source` and `query_type` for filtering and reporting dashboards
- `received_at DESC` for chronological message feeds
- `conversation_id` for threading all messages in a booking journey
- `action` and `reply_status` for agent queue views and SLA reporting
- `booking_ref` for fast reservation lookups

---

## Part 3 — Operational Thinking

### Immediate response (high-urgency complaint)

The guest-facing reply should: acknowledge the issue immediately by name, avoid sounding defensive, confirm that human escalation is already in progress, and make no promises about resolution time. Example:

> "Hi [Guest Name], I'm very sorry you're dealing with this issue, especially so late at night and before your guests arrive. I've immediately escalated this to our urgent support team and the Villa B1 caretaker for priority resolution. Someone will contact you shortly with an update and next steps. Thank you for your patience."

### System behaviour behind the reply

Beyond sending the message, the platform should automatically:

1. Classify the message as a high-priority complaint and set `action = escalate`.
2. Notify the on-call operations team, villa caretaker, and property manager via WhatsApp/SMS/email.
3. Create a `conversations` record with the booking reference, property ID, and full message history.
4. Start a 30-minute SLA timer for human acknowledgement.

If no human responds within 30 minutes: re-escalate to a secondary manager, trigger repeated alerts, and mark the incident as `sla_breached` for operational reporting. All escalation events and timestamps remain auditable via `message_responses.sent_at` and `reply_status`.

### Pattern detection and learning

Three similar hot-water complaints in two months signals a recurring operational failure, not isolated guest dissatisfaction. The platform should:

- Detect repeated complaint patterns grouped by `property_id` and `query_type` over rolling time windows.
- Trigger preventive maintenance recommendations when a threshold is crossed (e.g. 2+ complaints of the same category within 60 days).
- Generate operational alerts for management review before the next guest arrives.

With more time, I would build complaint trend analytics, automatic maintenance ticket generation, and threshold-based anomaly detection. This shifts the system from reactive guest support toward proactive operations management.

---

## What I Would Add With More Time

- **Multi-property support** — resolve `PROPERTY_CONTEXT` by `property_id` from a config store or DB row.
- **Retry with exponential backoff** — wrap the Anthropic API call with `tenacity` for transient 529/503 errors.
- **Structured logging with request IDs** — propagate `message_id` through every log line for trace-level debugging.
- **Streaming reply** — stream Claude's output to reduce perceived latency on long replies.
- **Webhook signature verification** — validate HMAC signatures for Airbnb/Booking.com webhooks before processing.
- **Rate limiting** — per-`source` throttle to prevent abuse from any single channel.
- **Async DB persistence** — write `inbound_messages` + `message_responses` rows after responding, using `asyncpg`, without blocking the HTTP response.
- **SLA timer service** — a background worker that checks `sent_at` against escalation thresholds and fires secondary alerts.
- **Complaint trend analytics** — aggregate `query_type = complaint` by `property_id` over time and surface anomalies to operations.
