# Deploying to a public URL (Render — free tier)

This repo includes a `render.yaml` so Render can configure itself
automatically ("Infrastructure as Code"). No Docker required.

## Steps

1. **Push this project to a GitHub repository** (if you haven't already):
   ```bash
   cd issue-reporter-chatbot
   git init
   git add .
   git commit -m "Issue reporting chatbot prototype"
   git branch -M main
   git remote add origin https://github.com/<your-username>/<your-repo>.git
   git push -u origin main
   ```

2. **Create a free Render account** at https://render.com (sign in with GitHub
   is fastest).

3. **New → Blueprint** (this is the option that reads `render.yaml`
   automatically):
   - Connect your GitHub account if prompted.
   - Select the repository you just pushed.
   - Render will detect `render.yaml` and pre-fill the service config
     (build command, start command, free plan).
   - Leave `OPENAI_API_KEY` blank unless you want LLM-based classification —
     the app works fully without it.
   - Click **Apply** / **Create Web Service**.

4. **Wait for the build** (1–3 minutes on the free tier). Render will show
   build logs live.

5. **Done.** Render gives you a public URL like:
   ```
   https://issue-reporter-chatbot.onrender.com
   ```
   Open it — you'll see the same chat interface, now live on the internet.

## If you'd rather not use the Blueprint button

Manually create a **New → Web Service** and set:
- **Build Command:** `pip install -r backend/requirements.txt`
- **Start Command:** `cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT`
- **Plan:** Free

## Important notes about the free tier

- **Spin-down:** Render's free web services spin down after ~15 minutes of
  inactivity and take ~30–50 seconds to wake back up on the next request.
  This is normal — if your demo video shows a delay on first load, that's why.
- **Ephemeral disk:** The free tier's filesystem is **not persistent across
  deploys/restarts**. That means the SQLite file (`chatbot.sqlite3`) can be
  wiped if the service restarts or redeploys. This is fine for a take-home
  demo, but for anything long-lived you'd want to either:
  - upgrade to a Render persistent disk, or
  - swap SQLite for a managed Postgres instance (Render offers a free
    Postgres tier too — see `docs/ASSUMPTIONS_AND_FUTURE.md` for the planned
    migration path).
- Alternatives to Render with a similar free-tier flow: **Railway** and
  **Fly.io** both work the same way (connect GitHub repo, set the same build/
  start commands).
