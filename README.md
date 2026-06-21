# Issue Desk — Issue Reporting Chatbot

A chatbot prototype that helps users report issues they encounter in an
application. It collects the issue description, page/module, error message,
time of occurrence, and (optional) user contact details through a guided
conversation, classifies the issue into a category, generates a structured
support ticket, and stores everything in a database.

![Architecture Diagram](docs/architecture-diagram.svg)

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | React 18 (via CDN, no build step) + plain CSS |
| Backend | Python 3.10+, FastAPI |
| Database | SQLite (file-based, zero setup) |
| AI Integration | Rule-based keyword classifier by default; optional OpenAI API call if `OPENAI_API_KEY` is set |
| Server | Uvicorn (ASGI) |

> The frontend uses React via CDN script tags instead of a Next.js build
> pipeline so the whole project can be cloned and run with no `npm install`
> step. See `docs/ASSUMPTIONS_AND_FUTURE.md` for the reasoning and how to
> upgrade to a full Next.js build later.

## Project structure

```
issue-reporter-chatbot/
├── backend/
│   ├── main.py            # FastAPI app, conversation engine, classifier, DB
│   ├── requirements.txt
│   └── chatbot.sqlite3    # created automatically on first run
├── frontend/
│   └── index.html         # single-file React chat UI
├── docs/
│   ├── ARCHITECTURE.md
│   ├── architecture-diagram.svg
│   └── ASSUMPTIONS_AND_FUTURE.md
└── README.md
```

## Setup instructions

### Prerequisites
- Python 3.10+
- pip

### 1. Clone the repo
```bash
git clone <your-repo-url>
cd issue-reporter-chatbot
```

### 2. Install backend dependencies
```bash
cd backend
pip install -r requirements.txt
```

### 3. (Optional) Enable LLM-based classification
The app works fully without this — it falls back to a built-in rule-based
classifier. Only do this if you have an OpenAI API key and want LLM-based
classification instead.

```bash
cp .env.example .env
```
Then open `backend/.env` and replace the placeholder with your real key:
```
OPENAI_API_KEY=sk-your-real-key-here
```
The app loads this file automatically on startup — no terminal export needed.

### 4. Run the server
```bash
uvicorn main:app --reload --port 8000
```

### 5. Open the app
Visit **http://127.0.0.1:8000** in your browser. The chat UI is served
directly by the backend, so there's nothing else to start.

### 6. View stored tickets / conversations (for grading/demo)
```bash
# All tickets
curl http://127.0.0.1:8000/api/tickets

# A specific ticket
curl http://127.0.0.1:8000/api/tickets/TCK-XXXXXXXX

# Full transcript of a session
curl http://127.0.0.1:8000/api/conversations/<session_id>
```

Or just inspect `backend/chatbot.sqlite3` with any SQLite browser
(e.g. [DB Browser for SQLite](https://sqlitebrowser.org/)).

## How it works (quick tour)

1. Open the page — the bot greets you and asks you to describe the issue.
2. As soon as you describe it, the bot tentatively classifies the issue
   (Login Issue, Payment Issue, Technical Bug, Feature Request, Performance
   Issue, UI/UX Issue, or Other) and asks where it happened.
3. It then asks for any error message, when it happened, and optional
   contact details — you can type `skip` or `no` to leave any of these blank.
4. It shows you a full structured summary and asks for confirmation.
5. On confirmation, a ticket is created (e.g. `TCK-93CC5F49`) and persisted
   to SQLite, along with the full conversation transcript.

See `docs/ARCHITECTURE.md` for the full flow diagram and data model, and
`docs/ASSUMPTIONS_AND_FUTURE.md` for assumptions and what would be built
next with more time. To put this on a public URL, see `docs/DEPLOYMENT.md`
(free Render deploy, ~5 minutes, `render.yaml` included).

## Tests performed

The conversation flow was exercised end-to-end via the API (see
`docs/ARCHITECTURE.md`) confirming: correct category classification,
all follow-up questions firing in order, skip/no handling for optional
fields, ticket creation, and correct persistence to SQLite.
