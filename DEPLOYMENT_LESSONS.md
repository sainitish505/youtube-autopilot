# Deployment Lessons Learned

Every mistake made during the Railway + Vercel deployment of this project, so they never happen again.

---

## 1. `NEXT_PUBLIC_*` vars must be saved in Vercel project settings — not just passed at deploy time

**What went wrong:** Ran `vercel deploy --prod --env NEXT_PUBLIC_API_URL=https://...` which only applies to that single build. The variable was never saved to the project. The next deploy (or any user visiting the site) got the fallback `localhost:8000` baked in.

**Rule:** Always add persistent env vars with `vercel env add` first, then deploy.

```bash
# Correct order:
echo "https://your-api.up.railway.app" | vercel env add NEXT_PUBLIC_API_URL production
vercel deploy --prod --yes
```

**Verify:** After deploying, confirm with `vercel env ls` — the var must appear there, not just in the build output.

---

## 2. `NEXT_PUBLIC_*` vars are baked in at BUILD TIME — changing them requires a redeploy

**What went wrong:** Updated the env var in Vercel dashboard but the old build was still being served with `localhost:8000` inside the JS bundle.

**Rule:** Any change to a `NEXT_PUBLIC_*` variable requires a full redeploy (`vercel deploy --prod --yes`). Saving the var in the dashboard is not enough on its own.

---

## 3. `passlib` is incompatible with `bcrypt >= 4.x` — remove passlib entirely

**What went wrong:** `requirements-api.txt` had `passlib[bcrypt]` which installs bcrypt as a dependency. Different bcrypt versions break in different ways:
- `bcrypt 5.x` → `AttributeError: module 'bcrypt' has no attribute '__about__'`
- `bcrypt 4.x` → `ValueError: password cannot be longer than 72 bytes` (passlib's `detect_wrap_bug` test uses >72-byte test vectors which bcrypt 4.x now rejects)

**Rule:** Never use `passlib`. Use `bcrypt` directly.

```python
import bcrypt

# Hash
pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

# Verify
bcrypt.checkpw(password.encode(), stored_hash.encode())
```

Add to requirements: `bcrypt>=4.0.1` (no passlib).

---

## 4. FastAPI needs a `lifespan` startup event to create DB tables on first deploy

**What went wrong:** Railway's PostgreSQL is empty on first deploy. SQLAlchemy models don't auto-create tables unless you explicitly call `create_all`. The app started fine but every DB request 500'd with `relation "user_profiles" does not exist`.

**Rule:** Always add a lifespan event in `api/main.py`:

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(lifespan=lifespan, ...)
```

---

## 5. Railway's `$PORT` env var must be used — never hardcode a port in the Dockerfile

**What went wrong:** `Dockerfile.api` had `CMD ["uvicorn", ..., "--port", "8000"]`. Railway injects a dynamic `$PORT` and health-checks it. The container started but Railway couldn't reach it.

**Rule:** Always use `${PORT:-8000}` in Docker CMD:

```dockerfile
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2"]
```

---

## 6. `load_dotenv()` must be called at the top of `api/main.py` — before any imports

**What went wrong:** `YOUTUBE_CLIENT_ID` and other vars were read at module-level (`os.environ.get(...)`) in router files. When uvicorn started without `.env` loaded, all those vars were empty strings. The OAuth connect button showed "not configured" even though `.env` had the right values.

**Rule:** Load `.env` before anything else in `api/main.py`:

```python
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)

# Only then import routers (which read os.environ at import time)
from api.routers import auth, jobs, ...
```

---

## 7. YouTube OAuth requires a **Web application** credential — not Desktop/Installed

**What went wrong:** Used `client_secrets.json` which was type `"installed"` (Desktop app). Desktop credentials only allow `redirect_uri=http://localhost` (no port, no path). Our callback at `http://localhost:8000/api/youtube/callback` caused Google to return HTTP 500 on the consent page.

**Rule:** For any server-side OAuth callback:
1. Go to Google Cloud Console → Credentials → **Create OAuth 2.0 Client ID**
2. Application type: **Web application** (not Desktop)
3. Add the exact callback URL under **Authorised redirect URIs**
4. Use the `client_id` and `client_secret` from this credential in `.env`

---

## 8. OAuth redirect URIs must be URL-encoded properly — use `urllib.parse.urlencode`

**What went wrong:** Built the OAuth URL with manual f-string concatenation. The scope `https://www.googleapis.com/auth/youtube.upload` embedded raw in `&scope=...` — Google's parser misread the `://` and returned `invalid_scope`.

**Rule:** Always use `urlencode` for OAuth query parameters:

```python
from urllib.parse import urlencode

params = {
    "client_id": CLIENT_ID,
    "redirect_uri": REDIRECT_URI,
    "scope": "https://www.googleapis.com/auth/youtube.upload",
    "response_type": "code",
    "access_type": "offline",
    "prompt": "consent",
    "state": state,
}
auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
```

---

## 9. Never pass `scopes=` when building `google.oauth2.credentials.Credentials` from a refresh token

**What went wrong:** The `Credentials` object was built with `scopes=["https://www.googleapis.com/auth/youtube.upload"]`. When `.refresh()` was called, Google's token endpoint received a `scope` parameter that didn't match what was originally granted — `invalid_scope`.

**Rule:** When constructing `Credentials` from a stored refresh token, omit `scopes` entirely:

```python
creds = Credentials(
    token=None,
    refresh_token=refresh_token,
    token_uri="https://oauth2.googleapis.com/token",
    client_id=client_id,
    client_secret=client_secret,
    scopes=None,  # scope is baked into the refresh token already
)
creds.refresh(Request())
```

---

## 10. A git repo nested inside another git repo becomes a submodule — its files won't be committed

**What went wrong:** `nextjs-frontend/` had its own `.git` folder. When the parent repo ran `git add nextjs-frontend/`, Git treated it as a submodule reference (mode `160000`) instead of tracking the files. The GitHub repo had an empty `nextjs-frontend` directory — Vercel had nothing to build.

**Rule:** Before `git init` on the parent repo, remove any nested `.git` folders:

```bash
rm -rf nextjs-frontend/.git
git add nextjs-frontend/
# Verify files are tracked (not 160000 mode):
git ls-files --stage nextjs-frontend | head -3
# Should show 100644, not 160000
```

---

## 11. Port 8000 gets taken by other processes — always use 8001 for this project locally

**What went wrong:** Restarted the dev machine or other apps; port 8000 was grabbed by a different service (`jobhelper_api`). The frontend silently called the wrong app and got 404s.

**Rule:** This project's local API runs on **port 8001**. `.env.local` is set to `NEXT_PUBLIC_API_URL=http://localhost:8001`. To start:

```bash
cd /Users/parvezlasi/HOPEAI/youtube_agent
source venv/bin/activate
uvicorn api.main:app --host 0.0.0.0 --port 8001
```

To kill a stale process on the port: `lsof -ti :8001 | xargs kill -9`

---

## 12. Always restart the API after changing `.env` — module-level vars are frozen at import time

**What went wrong:** Added `YOUTUBE_CLIENT_ID` to `.env` but the API was still running with the old (empty) value. The settings page showed "YouTube OAuth not configured" even after saving the env file.

**Rule:** Any change to `.env` requires killing and restarting the uvicorn process. Variables read at module level (`YOUTUBE_CLIENT_ID = os.environ.get(...)` at the top of a router file) are evaluated once at import time — they don't re-read the file on each request.

---

## Quick-Start Checklist (Local Dev)

```bash
# 1. Start local services (once per machine boot)
brew services start postgresql@14
brew services start redis

# 2. Start API (port 8001 — not 8000, that's taken by another app)
cd /Users/parvezlasi/HOPEAI/youtube_agent
source venv/bin/activate
uvicorn api.main:app --host 0.0.0.0 --port 8001

# 3. Start frontend (in a separate terminal)
cd nextjs-frontend
npm start   # serves on port 3000
```

## Quick-Start Checklist (Deploy to Production)

```bash
# 1. Set any new env vars in Vercel BEFORE deploying
echo "value" | vercel env add VAR_NAME production

# 2. Deploy frontend
cd nextjs-frontend && vercel deploy --prod --yes

# 3. Deploy API/worker to Railway
cd .. && railway up --service api --detach

# 4. Verify
curl https://api-production-4829.up.railway.app/health
```
