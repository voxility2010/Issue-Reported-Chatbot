# Architecture

## Component diagram

![Architecture Diagram](architecture-diagram.svg)

```
USER (browser)
  |
  ▼
FRONTEND — React chat UI (single HTML file, CDN React, no build step)
  |   HTTP POST /api/chat  { session_id, message }
  ▼
BACKEND — FastAPI
  ├── Conversation State Machine   (decides next question / next state)
  ├── Issue Classifier             (Groq API call — Llama 3.3 70B; classifies
  |                                  issue category & extracts structured details)
  └── Ticket Generator             (assembles structured ticket JSON)
  |
  ▼
STORAGE — SQLite
  ├── conversations table   (every user/bot turn, for audit & analytics)
  └── tickets table         (final structured ticket, JSON + columns)

Required: Groq API — GROQ_API_KEY must be set in the environment.
Used for issue classification and detail extraction via Llama 3.3 70B.
The app will not classify issues correctly without it.
```

## Conversation flow (state machine)

```
GREETING
   │  (bot greets user)
   ▼
AWAIT_DESCRIPTION ───► classify_issue(text) sets tentative category
   │                   extract_page_module / extract_error_message / extract_time
   │                   scan the description and auto-fill any fields they find,
   │                   removing those from the "pending" list
   ▼
COLLECTING  ───► asks only for whatever is still in session["pending"]
   │             (page_module → error_message → occurred_at, in that order,
   │              skipping any already auto-filled from the description)
   ▼
AWAIT_USER_DETAILS  ───► optional, user may skip
   ▼
CONFIRM  ───► bot shows full structured summary, asks yes/no
   │
   ├── "yes" ──► ticket saved to DB, ticket_ref returned ──► DONE
   └── "no"  ──► data discarded, loops back to AWAIT_DESCRIPTION
```

**Why this matters (requirement: "ask follow-up questions to gather missing
information"):** if a user's first message already says *"I got HTTP 500 on
the checkout page yesterday"*, the bot extracts the page, error code, and
time right there and skips straight to asking about contact details —
rather than re-asking for things the user already volunteered. If the user
gives a bare description with no extra detail, it falls back to asking all
three follow-up questions in sequence, same as before.

Each session is tracked by a `session_id` (a UUID generated client-side on
page load) and the backend keeps an in-memory dict of
`{session_id: {state, pending, current_field, data}}`. Every turn is also
written to the `conversations` table so the raw transcript is never lost
even if the in-memory session is cleared (e.g. server restart).

## Issue classification

`classify_issue()` in `backend/main.py`:

1. If `OPENAI_API_KEY` is set, it asks the LLM to pick one of the fixed
   category labels for the user's free-text description.
2. Otherwise (default, no key required), it scores the text against a
   keyword dictionary per category (`Login Issue`, `Payment Issue`,
   `Technical Bug`, `Feature Request`, `Performance Issue`, `UI/UX Issue`)
   and picks the highest-scoring category, defaulting to `Other`.

This two-tier design means the categorization step is **always functional**,
with the LLM as a drop-in quality upgrade rather than a hard dependency —
important for a prototype that should run without any paid API key.

## Data model (SQLite)

**conversations**
| column | type | notes |
|---|---|---|
| id | INTEGER PK | |
| session_id | TEXT | groups turns by chat session |
| role | TEXT | `user` or `bot` |
| message | TEXT | raw message text |
| created_at | TEXT | ISO timestamp |

**tickets**
| column | type | notes |
|---|---|---|
| id | INTEGER PK | |
| ticket_ref | TEXT | e.g. `TCK-93CC5F49`, shown to the user |
| session_id | TEXT | links back to the originating conversation |
| category | TEXT | classifier output |
| description | TEXT | user's issue description |
| page_module | TEXT | where it happened |
| error_message | TEXT | nullable |
| occurred_at | TEXT | free text or auto-filled timestamp |
| user_name / user_email | TEXT | nullable, optional contact info |
| status | TEXT | defaults to `Open` |
| created_at | TEXT | ISO timestamp |
| raw_json | TEXT | full structured payload, for forward-compatibility |
