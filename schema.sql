-- Nistula Guest Message Handler — persistence schema
-- PostgreSQL 14+

-- ---------------------------------------------------------------------
-- 1. Guest identity — unified across all inbound channels
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS guests (
    guest_id        UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    guest_name      TEXT        NOT NULL,
    primary_channel TEXT,                   -- whatsapp | booking_com | airbnb | instagram | direct
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
-- 2. Conversations — one booking journey, potentially many messages
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS conversations (
    conversation_id UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    guest_id        UUID        NOT NULL REFERENCES guests(guest_id) ON DELETE CASCADE,
    booking_ref     TEXT,
    property_id     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
-- 3. Inbound messages — every raw message normalised into this schema
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS inbound_messages (
    message_id      UUID        PRIMARY KEY,
    conversation_id UUID        REFERENCES conversations(conversation_id),
    source          TEXT        NOT NULL,   -- whatsapp | booking_com | airbnb | instagram | direct
    guest_name      TEXT        NOT NULL,
    message_text    TEXT        NOT NULL,
    timestamp       TIMESTAMPTZ NOT NULL,
    booking_ref     TEXT,
    property_id     TEXT,
    query_type      TEXT        NOT NULL,   -- see QueryType enum
    received_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
-- 4. AI responses — drafted reply, confidence, and routing action
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS message_responses (
    id                  UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id          UUID         NOT NULL REFERENCES inbound_messages(message_id) ON DELETE CASCADE,
    drafted_reply       TEXT         NOT NULL,
    final_reply         TEXT,                    -- populated if agent edits before sending
    reply_status        TEXT         NOT NULL DEFAULT 'drafted',  -- drafted | edited | auto_sent | agent_sent | escalated
    confidence_score    NUMERIC(5,4) NOT NULL CHECK (confidence_score BETWEEN 0 AND 1),
    action              TEXT         NOT NULL,   -- auto_send | agent_review | escalate
    claude_model        TEXT         NOT NULL,
    generated_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),
    sent_at             TIMESTAMPTZ             -- null until actually delivered
);

-- ---------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_messages_source          ON inbound_messages (source);
CREATE INDEX IF NOT EXISTS idx_messages_query_type      ON inbound_messages (query_type);
CREATE INDEX IF NOT EXISTS idx_messages_received        ON inbound_messages (received_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_conversation    ON inbound_messages (conversation_id);
CREATE INDEX IF NOT EXISTS idx_responses_action         ON message_responses (action);
CREATE INDEX IF NOT EXISTS idx_responses_confidence     ON message_responses (confidence_score);
CREATE INDEX IF NOT EXISTS idx_responses_status         ON message_responses (reply_status);
CREATE INDEX IF NOT EXISTS idx_conversations_guest      ON conversations (guest_id);
CREATE INDEX IF NOT EXISTS idx_conversations_booking    ON conversations (booking_ref);

-- ---------------------------------------------------------------------
-- Design notes
-- ---------------------------------------------------------------------
-- 1. guests stores unified guest identity across channels — one row per
--    person regardless of whether they contact via WhatsApp, Airbnb, etc.
-- 2. conversations groups multiple inbound messages under a single booking
--    journey, making it easy to read the full thread for any reservation.
-- 3. message_responses separates AI-generated output from inbound data and
--    tracks the full lifecycle: drafted → edited by agent → sent.
-- 4. reply_status + final_reply support the drafted / edited / auto_sent
--    distinction explicitly requested: drafted = Claude's raw output,
--    edited = agent modified it before sending, auto_sent = went out as-is.
-- 5. confidence_score and action provide a full audit trail for every
--    routing decision, supporting human-review workflows and reporting.


-- Hardest design decision:
-- Guest identity resolution across channels was the most difficult call.
-- A guest named "Rahul Sharma" on WhatsApp and "Rahul Sharma" on Airbnb
-- may or may not be the same person — there is no shared ID across platforms.
-- I chose to create a guests table with a generated UUID and store
-- guest_name + primary_channel, accepting that deduplication is a manual
-- or future ML problem rather than trying to solve it at the schema level
-- with fragile name-matching logic. The alternative — merging guest records
-- automatically by name — risks conflating different people and corrupting
-- conversation history, which is far more damaging than having duplicate
-- guest rows. This decision keeps the schema correct by default and leaves
-- identity resolution to a deliberate product decision later.
