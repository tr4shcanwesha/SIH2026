# HoneyChain FastAPI backend

Minimal FastAPI layer for Supabase authentication.

## Setup

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Fill `.env` with values from the Supabase project dashboard, then run:

```powershell
$env:SUPABASE_URL = "https://your-project-ref.supabase.co"
$env:SUPABASE_ANON_KEY = "your-supabase-anon-key"
$env:SUPABASE_SERVICE_ROLE_KEY = "your-supabase-service-role-key"
$env:FRONTEND_URL = "http://localhost:8000"
uvicorn app.main:app --reload --port 8000
```

Enable Google under Supabase Dashboard > Authentication > Providers > Google, and add the Supabase callback URL shown there. Add the frontend auth URL to the provider redirect allow list:

`http://localhost:8000/auth`

The FastAPI server serves both the API and the frontend. Open the application at
`http://localhost:8000/`; no separate frontend server is needed.

For the prototype admin login, use:

- Username: `honey`
- Password: `chain`

The public landing page is `/`. A successful login goes to the separate protected
homepage at `/homepage`, while `/dashboard` is also protected by the same session.

Endpoints:

- `GET /api/health` checks that the API is running.
- `GET /api/auth/config` returns only the public browser configuration.
- `GET /api/auth/session` validates a Supabase access token sent as a Bearer token.
