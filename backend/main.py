import json
import os
import sqlite3
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "chatbot.sqlite3"
FRONTEND_DIR = BASE_DIR.parent / "frontend"

load_dotenv(BASE_DIR / ".env")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

if not GROQ_API_KEY:
    print("⚠️  WARNING: GROQ_API_KEY is not set.")

app = FastAPI(title="Issue Reporting Chatbot API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_ref TEXT UNIQUE NOT NULL,
            session_id TEXT NOT NULL,
            category TEXT,
            description TEXT,
            page_module TEXT,
            error_message TEXT,
            occurred_at TEXT,
            user_name TEXT,
            user_email TEXT,
            status TEXT DEFAULT 'Open',
            created_at TEXT NOT NULL,
            raw_json TEXT
        );
    """)
    conn.commit()
    conn.close()


init_db()


def call_groq_json(system_prompt: str, user_prompt: str, temperature: float = 0) -> Optional[dict]:
    if not GROQ_API_KEY:
        return None
    try:
        payload = json.dumps({
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": 600,
            "response_format": {"type": "json_object"},
        }).encode()
        req = urllib.request.Request(
            "https://api.groq.com/openai/v1/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
                "User-Agent": "IssueDeskChatbot/1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read())
            content = body["choices"][0]["message"]["content"]
            return json.loads(content)
    except urllib.error.HTTPError as e:
        try:
            error_body = e.read().decode()
        except Exception:
            error_body = "<unreadable>"
        print(f"Groq HTTP {e.code}: {error_body}")
        return None
    except Exception as e:
        print(f"Groq call failed: {e}")
        return None


FIELD_ORDER = ["page_module", "error_message", "occurred_at"]

ISSUE_CATEGORIES = [
    "Login Issue", "Payment Issue", "Performance Issue",
    "Technical Bug", "Feature Request", "UI/UX Issue", "Other",
]

# Fixed questions asked by Python — LLM never composes questions, only extracts data.
FIELD_QUESTIONS = {
    "page_module": "Which page or screen did this happen on?",
    "error_message": "Did you see any error message or code? (Type 'no' if there wasn't one)",
    "occurred_at":   "Roughly when did this happen? (e.g. 'just now', 'yesterday' — or type 'skip')",
}

FIELD_GENTLE = {
    "page_module": "Just to confirm — which part of the app were you using when this happened?",
    "error_message": "No worries if you don't remember — any error text or just type 'no'?",
    "occurred_at":   "Any idea when this started? Even 'yesterday' or 'a few hours ago' helps. Type 'skip' if not sure.",
}


def new_session() -> dict:
    return {
        "state": "GREETING",
        "pending": list(FIELD_ORDER),
        "retry_count": 0,
        "clarification_attempts": 0,
        "accumulated_description": "",   # grows across clarification turns
        "current_field": None,
        "last_bot_message": None,
        "data": {
            "description": None,
            "page_module": None,
            "error_message": None,
            "occurred_at": None,
            "user_name": None,
            "user_email": None,
            "category": None,
        },
    }


SESSIONS: dict[str, dict] = {}


# --------------------------------------------------------------------------
# LLM helpers — pure extraction, no question-composing
# --------------------------------------------------------------------------

def llm_understand_description(text: str) -> dict:
    """
    Classifies the user's message and extracts any field data present.
    needs_more_detail is intentionally very hard to trigger — if there's ANY
    symptom word present, we accept it and move to structured collection.
    """
    system = (
        "You are the backend of a support chatbot. Read the user's message and return STRICT JSON:\n"
        "{\n"
        '  "is_real_description": boolean,\n'
        '  "needs_more_detail": boolean,\n'
        '  "detail_request_reply": string|null,\n'
        '  "user_wants_to_end": boolean,\n'
        '  "clarification_reply": string|null,\n'
        '  "clean_description": string,\n'
        f'  "category": string,\n'
        '  "page_module": string|null,\n'
        '  "error_message": string|null,\n'
        '  "occurred_at": string|null\n'
        "}\n\n"
        "RULES — read carefully:\n"
        f"category must be exactly one of: {ISSUE_CATEGORIES}\n\n"
        "is_real_description=false ONLY for: pure greetings (hi/hey/hello with nothing else), "
        "pure small talk, questions directed at us, or complete gibberish. "
        "If the user mentions ANY app-related problem — even one word like 'stuck', 'broken', "
        "'slow', 'not working', 'frozen', 'error' — is_real_description=true.\n\n"
        "needs_more_detail=true ONLY when the message is literally just a noun with ZERO symptom "
        "info — e.g. bare words like 'dashboard', 'checkout', 'login' with nothing else. "
        "The moment the user adds ANY symptom word (stuck, slow, frozen, broken, not loading, "
        "not working, error, crash, issue, problem, bug, can't, won't, doesn't) — "
        "needs_more_detail=false. When in doubt: false. We collect details in the next phase.\n\n"
        "user_wants_to_end=true if user clearly wants to leave without reporting "
        "('no', 'nothing', 'never mind', 'I'm good', 'all good', 'no issues', 'I'm fine', 'bye').\n\n"
        "clarification_reply: only if is_real_description=false. "
        "If user_wants_to_end=true, warmly say goodbye. Otherwise greet naturally and ask what's wrong.\n\n"
        "clean_description: restate the issue clearly in 1-2 sentences, fixing typos. "
        "Empty string if is_real_description=false.\n\n"
        "page_module: capture FULL location context — feature + parent page if implied. "
        "Examples: 'dashboard is stuck' → 'Dashboard'. "
        "'daily streak not updating' → 'Daily Streak on Dashboard'. "
        "'checkout keeps failing' → 'Checkout'. 'can't log in' → 'Login page'.\n\n"
        "error_message: ONLY an actual error message, error code, or alert/toast text shown "
        "on screen — e.g. '404 Not Found', 'Network Error', 'Payment Declined'. Do NOT use "
        "general symptom words like 'stuck', 'frozen', 'slow', 'not moving', 'not working' — "
        "those already belong in the description/category, not here. null if no distinct "
        "error text or code was mentioned.\n\n"
        "occurred_at: any time hint — 'yesterday', 'since morning', 'just now'. null if none."
    )
    result = call_groq_json(system, f"User message: \"{text}\"", temperature=0.3)
    if not result or "is_real_description" not in result:
        return {
            "is_real_description": True, "needs_more_detail": False,
            "detail_request_reply": None, "user_wants_to_end": False,
            "clarification_reply": None,
            "clean_description": text, "category": "Other",
            "page_module": None, "error_message": None, "occurred_at": None,
        }
    if result.get("category") not in ISSUE_CATEGORIES:
        result["category"] = "Other"
    return result


def llm_extract_fields(description: str, known_fields: dict, missing_fields: list,
                        user_text: str, last_asked_field: str = None) -> Optional[dict]:
    """
    Pure extraction — reads user's message, pulls values for still-missing fields.
    Returns ONLY field_updates. Python handles all question-asking.
    The LLM never asks anything, never probes, never sub-questions.
    """
    if not missing_fields:
        return {"field_updates": {}}

    field_hints = {
        "page_module": "which page/screen/feature the issue happened on (include parent page if implied)",
        "error_message": "any error message, code, or symptom description (frozen, crash, blank screen etc.)",
        "occurred_at":   "when it happened — any time reference counts",
    }
    missing_desc = "\n".join(f"  - {f}: {field_hints[f]}" for f in missing_fields)
    known_desc = "\n".join(f"  - {k}: {v}" for k, v in known_fields.items()) or "  none"

    system = (
        "You are a data extraction engine for a support chatbot. "
        "Your ONLY job is to extract field values from the user's message. "
        "Do NOT ask questions. Do NOT comment. Return STRICT JSON only:\n"
        '{"field_updates": {"page_module": ..., "error_message": ..., "occurred_at": ...}}\n\n'
        "For each field in field_updates:\n"
        '  - string value: if the message contains relevant info for that field (accept vague answers as-is)\n'
        '  - "SKIP": if user explicitly can\'t/won\'t provide it '
        "('I don't know', 'no error', 'I don't remember', 'not sure', 'skip', 'no idea')\n"
        "  - null: if this message doesn't address that field at all\n\n"
        f"The question you JUST asked the user was specifically about: "
        f"{last_asked_field or 'nothing in particular'}. If their message is a vague/blanket "
        "reply ('I don't remember', 'not sure', 'no idea', 'don't know') with no other specific "
        "info, apply SKIP ONLY to that field — they were answering THAT question, not declining "
        "every missing field at once. Only mark another field SKIP if they explicitly addressed "
        "it too in this same message.\n"
        "CRITICAL: Only extract values for STILL-MISSING fields. "
        "NEVER return a value for ALREADY-KNOWN fields — they are resolved, leave them null. "
        "If user's answer is vague but present (e.g. 'yesterday', 'some error', 'frozen'), "
        "accept it — do NOT return null just because it's imprecise. "
        "page_module: capture full context (feature + parent page) when implied.\n"
        "error_message: only count it if the user names a SPECIFIC message/code distinct from "
        "the general symptom already known. If they just repeat 'frozen'/'stuck'/'not working' "
        "(already captured in the description), treat that as SKIP — there's no new error info, "
        "not a new value. 'no error', 'I don't know' are also SKIP."
    )
    user_prompt = (
        f"ISSUE DESCRIPTION: \"{description}\"\n\n"
        f"ALREADY KNOWN (do NOT re-extract):\n{known_desc}\n\n"
        f"STILL MISSING (extract these only):\n{missing_desc}\n\n"
        f"USER'S MESSAGE: \"{user_text}\""
    )
    return call_groq_json(system, user_prompt, temperature=0.1)


def llm_parse_contact_message(user_text: str, current_data: dict) -> Optional[dict]:
    system = (
        "The user was asked for optional name/email for support follow-up. They might "
        "ALSO mention a correction or addition to their issue (e.g. recalling an error "
        "message). Return STRICT JSON only:\n"
        "{\n"
        '  "wants_to_skip": boolean,\n'
        '  "name": string|null,\n'
        '  "email": string|null,\n'
        '  "other_field_updates": {"page_module": string|null, "error_message": string|null, "occurred_at": string|null},\n'
        '  "reply_if_no_contact_given": string|null\n'
        "}\n"
        "name must be verbatim as typed, never fix spelling on it. "
        "wants_to_skip=true only for clear declines: 'no', 'skip', 'don't need to', 'nah'. "
        "'yes one sec', 'wait', 'hold on' = wants_to_skip=false, name=null (not a skip yet).\n"
        "other_field_updates: if the user mentions a correction/addition for any of these "
        "(even if already known — they may be correcting it), extract it; fix typos in "
        "error_message/page_module but never in name.\n"
        "reply_if_no_contact_given: ONLY if name/email/skip were NOT given — a short, warm "
        "reply. If they gave a field correction instead, acknowledge it specifically "
        "(e.g. 'Thanks, I've noted that error message!'), then re-ask for name/email. "
        "null if name/email/skip was given."
    )
    known_desc = ", ".join(f"{k}={v}" for k, v in current_data.items() if v) or "none yet"
    result = call_groq_json(
        system,
        f"Already known: {known_desc}\nUser reply: \"{user_text}\"",
        temperature=0.2,
    )
    return result


def llm_confirm_intent(text: str) -> Optional[bool]:
    system = (
        "User was shown a ticket summary and asked to confirm filing it. "
        'Return STRICT JSON: {"confirmed": true | false | null}\n'
        "true=yes/proceed, false=no/cancel/edit, null=ambiguous."
    )
    result = call_groq_json(system, f"User reply: \"{text}\"", temperature=0)
    if not result or "confirmed" not in result:
        return None
    return result["confirmed"]


def llm_classify_done_intent(text: str) -> dict:
    """After a ticket is filed, classify what the user wants: to end the
    conversation, ask about their existing ticket's status/timing, or
    report a brand new issue."""
    system = (
        "A support ticket was just filed for the user. Classify their next message. "
        'Return STRICT JSON only: {"intent": "end" | "status_question" | "new_issue"}\n\n'
        "end: clearly wrapping up — 'thanks', 'bye', 'that's all', 'I'm good', "
        "'nothing else', 'no', 'ok thanks'.\n\n"
        "status_question: asking about THIS ticket's status, timing, or follow-up — "
        "'when will I hear back', 'how long will this take', 'will someone contact me', "
        "'what happens now'.\n\n"
        "new_issue: describing a different/new problem, or saying they have another issue."
    )
    result = call_groq_json(system, f"User message: \"{text}\"", temperature=0)
    if not result or result.get("intent") not in {"end", "status_question", "new_issue"}:
        return {"intent": "new_issue"}
    return result


# --------------------------------------------------------------------------
# Persistence
# --------------------------------------------------------------------------

def log_message(session_id: str, role: str, message: str):
    conn = get_conn()
    conn.execute(
        "INSERT INTO conversations (session_id, role, message, created_at) VALUES (?, ?, ?, ?)",
        (session_id, role, message, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def save_ticket(session_id: str, data: dict) -> str:
    ticket_ref = "TCK-" + uuid.uuid4().hex[:8].upper()
    conn = get_conn()
    conn.execute(
        """INSERT INTO tickets
           (ticket_ref, session_id, category, description, page_module,
            error_message, occurred_at, user_name, user_email, created_at, raw_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            ticket_ref, session_id, data["category"], data["description"],
            data["page_module"], data["error_message"], data["occurred_at"],
            data["user_name"], data["user_email"],
            datetime.utcnow().isoformat(), json.dumps(data),
        ),
    )
    conn.commit()
    conn.close()
    return ticket_ref


# --------------------------------------------------------------------------
# Question helpers — Python asks, LLM only extracts
# --------------------------------------------------------------------------

def ask_field(field: str, gentle: bool = False) -> str:
    return FIELD_GENTLE[field] if gentle else FIELD_QUESTIONS[field]


def _reset_to_description(session: dict):
    fresh = new_session()
    session["data"] = fresh["data"]
    session["pending"] = fresh["pending"]
    session["retry_count"] = 0
    session["clarification_attempts"] = 0
    session["accumulated_description"] = ""
    session["state"] = "AWAIT_DESCRIPTION"

def build_summary(data: dict) -> str:
    name = data.get("user_name")
    email = data.get("user_email")
    if name and email:
        contact = f"{name} ({email})"
    elif email:
        contact = email
    elif name:
        contact = name
    else:
        contact = "Not provided"

    return (
        "Here's a summary of your report:\n\n"
        f"**Category:** {data['category']}\n"
        f"**Description:** {data['description']}\n"
        f"**Page/Module:** {data['page_module'] or 'Not specified'}\n"
        f"**Error message:** {data['error_message'] or 'None reported'}\n"
        f"**Time of occurrence:** {data['occurred_at'] or 'Not specified'}\n"
        f"**Contact:** {contact}"
    )


# --------------------------------------------------------------------------
# Main conversation engine
# --------------------------------------------------------------------------

MAX_CONTACT_RETRIES = 2


def handle_message(session_id: str, user_text: str) -> str:
    session = SESSIONS.setdefault(session_id, new_session())
    reply = _handle_message(session_id, user_text)
    session["last_bot_message"] = reply
    return reply


def _handle_message(session_id: str, user_text: str) -> str:
    session = SESSIONS.setdefault(session_id, new_session())
    state = session["state"]
    data = session["data"]
    text = user_text.strip()

    # ── GREETING ──────────────────────────────────────────────────────────
    if state == "GREETING":
        session["state"] = "AWAIT_DESCRIPTION"
        return "Hi! I'm here to help you report an issue. 🛠️\n\nCould you briefly describe the problem you're facing?"

    # ── AWAIT_DESCRIPTION ─────────────────────────────────────────────────
    if state == "AWAIT_DESCRIPTION":
        if not text:
            return "Could you describe the issue you're facing? Even a short sentence helps."

        # Accumulate context across clarification turns
        session["accumulated_description"] = (
            (session.get("accumulated_description", "") + " " + text).strip()
        )
        combined = session["accumulated_description"]

        understanding = llm_understand_description(combined)

        if understanding.get("user_wants_to_end"):
            session["state"] = "ENDED"
            return (understanding.get("clarification_reply") or
                    "No worries! Feel free to come back whenever you need to report something. Take care! 👋")

        if not understanding.get("is_real_description", True):
            return (understanding.get("clarification_reply") or
                    "Could you tell me what problem you're actually facing?")

        if understanding.get("needs_more_detail"):
            session["clarification_attempts"] = session.get("clarification_attempts", 0) + 1
            # Hard cap: after 1 clarification, just accept what we have
            if session["clarification_attempts"] >= 2:
                # Force-accept with what we've accumulated
                understanding["is_real_description"] = True
                understanding["needs_more_detail"] = False
                if not understanding.get("clean_description"):
                    understanding["clean_description"] = combined
                if not understanding.get("category") or understanding["category"] == "Other":
                    understanding["category"] = "Technical Bug"
            else:
                return (understanding.get("detail_request_reply") or
                        "Could you tell me a bit more — is it slow, showing an error, not loading, or something else?")

        # ── We have a valid description — commit it ──
        session["clarification_attempts"] = 0
        data["description"] = understanding.get("clean_description") or combined
        data["category"] = understanding.get("category", "Other")

        # Auto-fill fields the description already mentioned
        for field in FIELD_ORDER:
            val = understanding.get(field)
            if val and field in session["pending"]:
                data[field] = val
                session["pending"].remove(field)

        ack = f"Got it — sounds like a **{data['category']}**."

        if not session["pending"]:
            # All fields already extracted from description — jump to contact
            session["state"] = "AWAIT_USER_DETAILS"
            session["retry_count"] = 0
            contact_q = ("Last thing — would you like to share your name/email so our "
                         "support team can follow up? (Optional — type 'skip' to leave it out)")
            return ack + "\n\n" + contact_q

        session["state"] = "COLLECTING"
        session["current_field"] = session["pending"][0]
        return ack + "\n\n" + ask_field(session["pending"][0])

    # ── COLLECTING ────────────────────────────────────────────────────────
    if state == "COLLECTING":
        # Build known_fields: show ALL resolved fields including skipped ones
        known_fields_for_llm = {}
        for k in FIELD_ORDER:
            if k not in session["pending"]:
                known_fields_for_llm[k] = (
                    data[k] if data[k] else "[user said not available — do NOT re-ask]"
                )

        result = llm_extract_fields(
            description=data["description"] or "",
            known_fields=known_fields_for_llm,
            missing_fields=list(session["pending"]),
            user_text=text,
            last_asked_field=session.get("current_field"),
        )

        if not result:
            return "I'm having trouble processing that — could you try again?"

        updates = result.get("field_updates") or {}
        resolved_this_turn = []

        for f in FIELD_ORDER:
            val = updates.get(f)
            if val is None:
                continue
            if f not in session["pending"]:
                # Correction to already-resolved field
                if val != "SKIP":
                    data[f] = val
                continue
            # Resolve this pending field
            if val == "SKIP":
                if f == "occurred_at":
                    data[f] = datetime.utcnow().isoformat() + "Z (auto-filled)"
                elif f == "error_message":
                    data[f] = None  # no error reported — fine
                else:
                    data[f] = "Not specified"
            else:
                data[f] = val
            session["pending"].remove(f)
            resolved_this_turn.append(f)

        # Python owns all question-asking — never the LLM
        if session["pending"]:
            session["current_field"] = session["pending"][0]
            if not resolved_this_turn:
                return ask_field(session["pending"][0], gentle=True)
            return ask_field(session["pending"][0])

        # All fields done — move to contact details
        session["state"] = "AWAIT_USER_DETAILS"
        session["retry_count"] = 0
        contact_q = ("Last thing — would you like to share your name/email so our "
                     "support team can follow up? (Optional — type 'skip' to leave it out)")
        return "Got it, thanks!\n\n" + contact_q

# ── AWAIT_USER_DETAILS ────────────────────────────────────────────────
    if state == "AWAIT_USER_DETAILS":
        parsed = llm_parse_contact_message(text, {k: data[k] for k in FIELD_ORDER}) if text else None

        gave_contact = bool(
            parsed and (
                parsed.get("name") or
                parsed.get("email") or
                "@" in text
            )
        )
        wants_skip = bool(parsed and parsed.get("wants_to_skip"))

        if parsed:
            for f, val in (parsed.get("other_field_updates") or {}).items():
                if f in FIELD_ORDER and val:
                    data[f] = val

        if gave_contact or wants_skip or not parsed:
            data["user_name"] = parsed.get("name") if parsed else None
            raw_email = parsed.get("email") if parsed else None

            if not raw_email and "@" in text:
                raw_email = text.strip()

            data["user_email"] = raw_email
            session["state"] = "CONFIRM"
            return build_summary(data) + "\n\nShall I go ahead and file this ticket? (yes/no)"

        session["retry_count"] += 1
        if session["retry_count"] >= MAX_CONTACT_RETRIES:
            data["user_name"] = None
            data["user_email"] = None
            session["state"] = "CONFIRM"
            return build_summary(data) + "\n\nShall I go ahead and file this ticket? (yes/no)"

        return parsed.get("reply_if_no_contact_given") or (
            "Would you like to share your name or email so our team can follow up? "
            "(Just type 'skip' if not)"
        )
    # ── CONFIRM ───────────────────────────────────────────────────────────
    if state == "CONFIRM":
        confirmed = llm_confirm_intent(text)
        if confirmed is True:
            ticket_ref = save_ticket(session_id, data)
            session["state"] = "DONE"
            return (f"✅ Ticket **{ticket_ref}** has been created! Our support team "
                    "will get back to you soon.\n\n"
                    "Is there anything else you'd like to report, or are you all set?")
        elif confirmed is False:
            _reset_to_description(session)
            return "No problem, I've discarded that. What issue would you like to report?"
        else:
            return "Just to confirm — should I go ahead and file this ticket? (yes/no)"

    # ── DONE ──────────────────────────────────────────────────────────────
    if state == "DONE":
        if not text:
            return "Is there anything else you'd like to report?"
        intent = llm_classify_done_intent(text).get("intent", "new_issue")
        if intent == "end":
            session["state"] = "ENDED"
            return "You're all set! Thanks for reaching out — have a great day! 👋"
        if intent == "status_question":
            return ("Our support team typically gets back within 1–2 business days. "
                     "Is there anything else you'd like to report, or are you all set?")
        _reset_to_description(session)
        return _handle_message(session_id, text)

    # ── ENDED ─────────────────────────────────────────────────────────────
    if state == "ENDED":
        _reset_to_description(session)
        return "Welcome back! 👋 What issue would you like to report?"

    # Fallback
    _reset_to_description(session)
    return handle_message(session_id, text)


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------

class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    state: str


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    if req.message.strip():
        log_message(req.session_id, "user", req.message)
    reply = handle_message(req.session_id, req.message)
    log_message(req.session_id, "bot", reply)
    return ChatResponse(
        session_id=req.session_id,
        reply=reply,
        state=SESSIONS[req.session_id]["state"],
    )


@app.get("/api/health")
def health():
    llm_result = None
    llm_working = False
    if GROQ_API_KEY:
        llm_result = llm_understand_description("I cannot log in").get("category")
        llm_working = llm_result in ISSUE_CATEGORIES
    return {
        "api_key_loaded": bool(GROQ_API_KEY),
        "model": GROQ_MODEL,
        "llm_working": llm_working,
        "test_category": llm_result,
    }


@app.get("/api/tickets")
def list_tickets():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM tickets ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/tickets/{ticket_ref}")
def get_ticket(ticket_ref: str):
    conn = get_conn()
    row = conn.execute("SELECT * FROM tickets WHERE ticket_ref = ?", (ticket_ref,)).fetchone()
    conn.close()
    return dict(row) if row else {"error": "Ticket not found"}


@app.get("/api/conversations/{session_id}")
def get_conversation(session_id: str):
    conn = get_conn()
    rows = conn.execute(
        "SELECT role, message, created_at FROM conversations WHERE session_id = ? ORDER BY id",
        (session_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/")
def serve_frontend():
    return FileResponse(FRONTEND_DIR / "index.html")


app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
