# Nistula Guest Message Handler

A FastAPI service that receives inbound villa guest messages from any channel, classifies intent using Claude AI, drafts a property-aware reply, and routes the response based on a confidence score.

---

## Endpoint

```
POST /webhook/message
```

### Request

```json
{
  "source": "whatsapp",
  "guest_name": "Rahul Sharma",
  "message": "Is the villa available from April 20 to 24? What is the rate for 2 adults?",
  "timestamp": "2026-05-05T10:30:00Z",
  "booking_ref": "NIS-2024-0891",
  "property_id": "villa-b1"
}
```

`source` must be one of: `whatsapp`, `booking_com`, `airbnb`, `instagram`, `direct`

### Response

```json
{
  "message_id": "3f2a1c8e-...",
  "query_type": "pre_sales_availability",
  "drafted_reply": "Hi Rahul! Great news — Villa B1 is available from April 20 to 24...",
  "confidence_score": 0.88,
  "action": "auto_send"
}
```

---

## Query types

| Type | Example |
|---|---|
| `pre_sales_availability` | Is the villa available on these dates? |
| `pre_sales_pricing` | What is the rate for 2 adults 3 nights? |
| `post_sales_checkin` | What time can we check in? WiFi password? |
| `special_request` | Early check-in, airport transfer? |
| `complaint` | The AC is not working. I want a refund. |
| `general_enquiry` | Do you allow pets? Is there parking? |

---

## Action routing

| Condition | Action |
|---|---|
| `query_type == complaint` | `escalate` |
| `confidence < 0.60` | `escalate` |
| `0.60 ≤ confidence ≤ 0.85` | `agent_review` |
| `confidence > 0.85` | `auto_send` |

---

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Open .env and set ANTHROPIC_API_KEY=sk-ant-...
```

### 3. Run the server

```bash
uvicorn app.main:app --reload
```

API: `http://localhost:8000`  
Interactive docs: `http://localhost:8000/docs`

---

## Project structure

```
app/
  main.py                 # FastAPI app, /webhook/message route
  models/
    schemas.py            # Pydantic models (request, normalised, response)
  services/
    claude_service.py     # Claude call — classify + draft reply in one shot
    confidence.py         # Deterministic confidence scoring (no Claude)
    handler.py            # Orchestrator, Settings, UUID generation
    classifier.py         # Re-export shim (import compatibility)
schema.sql                # Optional PostgreSQL persistence schema
thinking.md               # Design decisions and trade-offs
requirements.txt
.env.example
```

---

## Configuration

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | **Required.** Anthropic API key. |
| `CLAUDE_MODEL` | `claude-sonnet-4-20250514` | Claude model to use. |
| `APP_VERSION` | `1.0.0` | Reported in server logs. |

---

## Design notes

See [`thinking.md`](thinking.md) for full design rationale, trade-offs, and planned improvements.
