# Assumptions & Future Improvements

## Assumptions made

1. **Groq (Llama 3.3 70B) is required.** A valid `GROQ_API_KEY` must be set
   in `backend/.env` for the chatbot to function. Without it, the LLM calls
   return `None` and the bot falls back to safe defaults — but classification,
   extraction, and intent detection will not work correctly. The key is free
   to obtain at [console.groq.com](https://console.groq.com).

2. **LLM does extraction only — Python owns the conversation flow.** The
   state machine in `main.py` decides what question to ask next and when to
   move states. Groq is called purely for classification and structured field
   extraction (page/module, error message, time of occurrence). The LLM never
   composes questions or drives the dialogue — this prevents it from going
   rogue with sub-questions or skipping steps.

3. **Single-process, in-memory session state.** Session state (`SESSIONS`
   dict) lives in the FastAPI process's memory. Restarting the server loses
   in-progress (unsubmitted) conversations, though every raw message is still
   logged to SQLite. Acceptable for a prototype; not for production.

4. **No authentication.** Anyone can open the chat and create tickets. There
   is no login system, rate limiting, or spam protection.

5. **SQLite over PostgreSQL.** Used to keep the project runnable with zero
   external setup. The schema is straightforward to port directly to
   PostgreSQL when needed.

6. **Contact info validation is minimal.** The LLM extracts name and email
   as typed — no format validation, deliverability check, or verification is
   performed.

7. **Single category per ticket.** Issues are classified into exactly one of
   seven categories. Multi-label classification is out of scope for this
   prototype.
## Future improvements

- **LLM-based slot extraction**: the current regex extraction (page/module,
  error codes, time phrases) handles common phrasings well, but an LLM-based
  extractor would generalize to phrasing the regexes miss, and could also
  pull out structured detail (browser, device, steps to reproduce) without
  adding new questions.
- **Persistent session store**: move `SESSIONS` into Redis or the database so
  in-progress conversations survive server restarts and scale across multiple
  backend instances.
- **Authentication & ownership**: tie tickets to logged-in user accounts so
  users can view their own ticket history, and support staff can be assigned
  tickets.
- **Admin dashboard**: a simple internal view (could reuse the same React
  setup) to list, filter, and update ticket status (`Open` → `In Progress` →
  `Resolved`).
- **Attachments**: allow users to upload a screenshot of the error, stored
  alongside the ticket.
- **Notifications**: email or Slack webhook when a new ticket is filed, and
  a confirmation email to the user if they provided one.
- **Multi-language support**: detect the user's language and respond
  accordingly, important for a global user base.
- **Analytics**: aggregate dashboards on ticket volume by category/page over
  time to surface recurring problem areas in the product.
- **Better duplicate detection**: check if a very similar issue was already
  reported recently and surface that instead of creating a near-duplicate
  ticket.
- **Production deployment**: containerize with Docker, add CI (GitHub
  Actions) to run tests and lint on every PR, and deploy backend + frontend
  separately (e.g. Render/Railway for the API, Vercel for a proper
  React/Next.js build of the frontend).
