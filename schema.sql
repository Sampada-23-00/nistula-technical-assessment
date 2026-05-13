-- Nistula Guest Message Handler — persistence schema
-- PostgreSQL 14+

CREATE TABLE IF NOT EXISTS inbound_messages (
    message_id      UUID        PRIMARY KEY,
    source          TEXT        NOT NULL,   -- whatsapp | booking_com | airbnb | instagram | direct
    guest_name      TEXT        NOT NULL,
    message_text    TEXT        NOT NULL,
    timestamp       TIMESTAMPTZ NOT NULL,
    booking_ref     TEXT,
    property_id     TEXT,
    query_type      TEXT        NOT NULL,   -- see QueryType enum
    received_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS message_responses (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id          UUID        NOT NULL REFERENCES inbound_messages(message_id) ON DELETE CASCADE,
    drafted_reply       TEXT        NOT NULL,
    confidence_score    NUMERIC(5,4) NOT NULL CHECK (confidence_score BETWEEN 0 AND 1),
    action              TEXT        NOT NULL,   -- auto_send | agent_review | escalate
    claude_model        TEXT        NOT NULL,
    generated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Useful indexes
CREATE INDEX IF NOT EXISTS idx_messages_source       ON inbound_messages (source);
CREATE INDEX IF NOT EXISTS idx_messages_query_type   ON inbound_messages (query_type);
CREATE INDEX IF NOT EXISTS idx_messages_received     ON inbound_messages (received_at DESC);
CREATE INDEX IF NOT EXISTS idx_responses_action      ON message_responses (action);
CREATE INDEX IF NOT EXISTS idx_responses_confidence  ON message_responses (confidence_score);
