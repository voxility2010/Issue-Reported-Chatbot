# Assumptions & Future Improvements

## Assumptions made

1. **No mandatory paid API key.** The brief suggests an LLM, but a prototype
   that hard-requires a paid key is hard to evaluate/demo. The classifier
   defaults to a rule-based keyword matcher and only calls OpenAI if
   `OPENAI_API_KEY` is present, so the project runs end-to-end for free.
2. **Lightweight regex extraction, not full NLU.** The bot scans the user's
   first message for page/module mentions, error codes, and time phrases and
   skips those questions if found — but this is pattern matching (e.g. "on
   the X page", "error 500", "yesterday"), not a general-purpose language
   understanding model. Phrasing outside these patterns won't be picked up,
   and it will simply ask the question normally in that case.
3. **Single-process, in-memory session state.** Session state (`SESSIONS`
   dict) lives in the FastAPI process's memory. Restarting the server loses
   in-progress (unsubmitted) conversations, though every raw message is
   still logged to SQLite. Acceptable for a prototype; not for production.
4. **No authentication.** Anyone can open the chat and create tickets. There's
   no login system, rate limiting, or spam protection.
5. **SQLite over PostgreSQL.** SQLite was used instead of PostgreSQL (the
   suggested alternative) to keep the project runnable with zero external
   setup. The schema is simple enough to port directly to PostgreSQL.
6. **Email/name validation is minimal.** The optional "user details" field
   just checks for an `@` to decide if it looks like an email; no real
   validation or verification is performed.
7. **Single category per ticket.** Issues are assumed to fall into exactly
   one category; multi-label classification is out of scope for the prototype.

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
