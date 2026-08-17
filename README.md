<div align="center">

# 🤖 Issue Reporting Chatbot

### Guided AI-Powered Issue Reporting & Support Ticket Generation

*A chatbot prototype that helps users report issues they encounter in an application. It collects the issue description, page/module, error message, time of occurrence, and optional user contact details through a guided conversation, classifies the issue using Groq's Llama 3.3 70B, generates a structured support ticket, and stores everything in SQLite.*

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![React](https://img.shields.io/badge/frontend-React%2018-61DAFB.svg)
![FastAPI](https://img.shields.io/badge/backend-FastAPI-009688.svg)
![SQLite](https://img.shields.io/badge/database-SQLite-003B57.svg)
![Groq](https://img.shields.io/badge/AI-Groq%20Llama%203.3%2070B-orange.svg)
![Uvicorn](https://img.shields.io/badge/server-Uvicorn-purple.svg)

</div>

---

## 📊 At a Glance

| | |
|---|---|
| 🤖 **AI model** | Groq — Llama 3.3 70B |
| 💬 **Interaction** | Guided conversational issue reporting |
| 🖥️ **Frontend** | React 18 via CDN + plain CSS |
| ⚙️ **Backend** | Python 3.10+ + FastAPI |
| 🗄️ **Database** | SQLite (file-based, zero setup) |
| 🚀 **Server** | Uvicorn (ASGI) |
| 🎫 **Output** | Structured support ticket + conversation transcript |
| 🔑 **API requirement** | Groq API key |

---

## 🏗️ 1. Architecture

![Architecture Diagram](docs/architecture-diagram.svg)

```text
User
 │
 ▼
React 18 Chat UI
 │
 ▼
FastAPI Backend
 │
 ▼
Conversation Engine
 │
 ├── Collect issue description
 │
 ├── Groq classification
 │      └── Llama 3.3 70B
 │
 ├── Collect page / module
 │
 ├── Collect error message
 │
 ├── Collect time of occurrence
 │
 └── Collect optional contact details
 │
 ▼
Structured Issue Summary
 │
 ▼
User Confirmation
 │
 ▼
Ticket Generation
 │
 ├── Ticket ID
 ├── Issue category
 ├── Issue details
 └── Conversation transcript
 │
 ▼
SQLite Database
```

> The frontend uses React via CDN script tags instead of a Next.js build pipeline so the whole project can be cloned and run with no `npm install` step. See `docs/ASSUMPTIONS_AND_FUTURE.md` for the reasoning and how to upgrade to a full Next.js build later.

---

## 🛠️ 2. Tech Stack

| Layer | Technology |
|---|---|
| 🖥️ **Frontend** | React 18 (via CDN, no build step) + plain CSS |
| ⚙️ **Backend** | Python 3.10+, FastAPI |
| 🗄️ **Database** | SQLite (file-based, zero setup) |
| 🤖 **AI Integration** | Groq API — Llama 3.3 70B for issue classification & detail extraction |
| 🚀 **Server** | Uvicorn (ASGI) |

---

## 📁 3. Project Structure

<details>
<summary>Click to expand</summary>

```text
issue-reporter-chatbot/
├── backend/
│   ├── main.py            # FastAPI app, conversation engine, Groq classifier, DB
│   ├── requirements.txt
│   ├── .env.example       # template for your Groq API key
│   └── chatbot.sqlite3    # created automatically on first run
├── frontend/
│   └── index.html         # single-file React chat UI
├── docs/
│   ├── ARCHITECTURE.md
│   ├── architecture-diagram.svg
│   ├── ASSUMPTIONS_AND_FUTURE.md
│   └── DEPLOYMENT.md
├── render.yaml             # one-click Render Blueprint config
└── README.md
```

</details>

---

## ⚙️ 4. Setup Instructions

### Prerequisites

- Python 3.10+
- pip
- A free **Groq API key** → [console.groq.com/keys](https://console.groq.com/keys)

### 1. Clone the repo

```bash
git clone https://github.com/voxility2010/Issue-Reported-Chatbot.git
cd Issue-Reported-Chatbot
```

### 2. Install backend dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 3. Set your Groq API key

This app uses Groq's **Llama 3.3 70B** model to classify issues and extract details from natural conversation — it is **required**, not optional.

```bash
cp .env.example .env
```

Open `backend/.env` and add your real key:

```text
GROQ_API_KEY=gsk_your-real-key-here
```

The app loads this file automatically on startup — no terminal export needed.

### 4. Run the server

```bash
uvicorn main:app --reload --port 8000
```

### 5. Open the app

Visit **http://127.0.0.1:8000** in your browser.

The chat UI is served directly by the backend, so there's nothing else to start.

---

## 🚀 5. How It Works

1. Open the page — the bot greets you and asks you to describe the issue.
2. As soon as you describe it, the bot uses Groq (Llama 3.3 70B) to classify the issue (Login Issue, Payment Issue, Technical Bug, Feature Request, Performance Issue, UI/UX Issue, or Other) and asks where it happened.
3. It then asks for any error message, when it happened, and optional contact details — you can type `skip` or `no` to leave any of these blank.
4. It shows you a full structured summary and asks for confirmation.
5. On confirmation, a ticket is created (e.g. `TCK-93CC5F49`) and persisted to SQLite, along with the full conversation transcript.

---

## 🧠 6. Issue Classification

The chatbot uses **Groq's Llama 3.3 70B** to classify the reported issue into a category and extract relevant details from the natural conversation.

| Category |
|---|
| 🔐 **Login Issue** |
| 💳 **Payment Issue** |
| 🐛 **Technical Bug** |
| ✨ **Feature Request** |
| ⚡ **Performance Issue** |
| 🎨 **UI/UX Issue** |
| 📌 **Other** |

---

## 🎫 7. Ticket Generation

After collecting the required information, the chatbot displays a full structured summary and asks the user for confirmation.

Once confirmed, a ticket is generated.

Example:

```text
TCK-93CC5F49
```

The ticket and the full conversation transcript are persisted to SQLite.

---

## 🗄️ 8. Database & API

SQLite is used as a file-based database, requiring zero additional database setup.

The database is automatically created at:

```text
backend/chatbot.sqlite3
```

### View all tickets

```bash
curl http://127.0.0.1:8000/api/tickets
```

### View a specific ticket

```bash
curl http://127.0.0.1:8000/api/tickets/TCK-XXXXXXXX
```

### View a full conversation transcript

```bash
curl http://127.0.0.1:8000/api/conversations/<session_id>
```

Or inspect `backend/chatbot.sqlite3` directly with any SQLite browser (e.g. [DB Browser for SQLite](https://sqlitebrowser.org/)).

---

## 🧪 9. Tests Performed

The conversation flow was exercised end-to-end via the API (see `docs/ARCHITECTURE.md`), confirming:

| Test | Result |
|---|:---:|
| Correct category classification via Groq (Llama 3.3 70B) | ✅ |
| All follow-up questions firing in the correct order | ✅ |
| `skip` / `no` handling for optional fields | ✅ |
| Ticket creation and ID generation | ✅ |
| Correct persistence of tickets and transcripts to SQLite | ✅ |

<div align="center">

**🎉 End-to-end conversation flow verified**

</div>

---

## 📚 10. Documentation

Additional documentation is available in the `docs/` directory:

| File | Description |
|---|---|
| `docs/ARCHITECTURE.md` | Full flow diagram and data model |
| `docs/architecture-diagram.svg` | Architecture diagram |
| `docs/ASSUMPTIONS_AND_FUTURE.md` | Assumptions and what would be built next with more time |
| `docs/DEPLOYMENT.md` | Deployment documentation |

---

## 🌐 11. Deployment

The repository includes a `render.yaml` configuration for a one-click Render Blueprint deployment.

The application can also be run locally using the setup instructions above.

---

## 📋 12. More Info

| | |
|---|---|
| 🤖 **AI Model** | Groq — Llama 3.3 70B |
| 🖥️ **Frontend** | React 18 via CDN + plain CSS |
| ⚙️ **Backend** | FastAPI |
| 🗄️ **Database** | SQLite |
| 🚀 **Server** | Uvicorn |
| 🔑 **API** | Groq API |
| 🎫 **Output** | Structured support tickets + transcripts |
| 📖 **Documentation** | Architecture, assumptions/future, deployment |

---

<div align="center">

*Built for issue reporting and support ticket automation.*

</div>
