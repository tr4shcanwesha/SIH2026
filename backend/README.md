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

## Database schema and data rules

Use Supabase PostgreSQL with the following schemas exactly for data storage. Do
not replace these tables, column names, types, primary keys, or foreign keys with
an alternative schema.

### `public.hives`

```sql
create table public.hives (
	hive_id text not null,
	location text not null,
	bee_species text not null,
	hive_type text not null,
	installation_date date not null,
	status text null default 'Healthy'::text,
	beekeeper_id text null,
	constraint hives_pkey primary key (hive_id),
	constraint hives_beekeeper_id_fkey foreign KEY (beekeeper_id) references beekeeper (beekeeper_id)
) TABLESPACE pg_default;
```

Every beekeeper's hives must be fetched from `public.hives` using the logged-in
beekeeper's `beekeeper_id` and displayed in the beekeeper's hive views.

### `public.beekeeper`

```sql
create table public.beekeeper (
	beekeeper_id text not null,
	name text not null,
	email text not null,
	phone text null,
	location text null,
	constraint beekeeper_pkey primary key (beekeeper_id)
) TABLESPACE pg_default;
```

Google/Gmail is the only login method for now. After login, compare the user's
Gmail address with `public.beekeeper.email`. If a matching email exists, fetch
and use that beekeeper's complete row. If no matching email exists, create a new
beekeeper row and then use the newly created beekeeper record for subsequent
requests.

### `public.honey_batches`

```sql
create table public.honey_batches (
	batch_id text not null,
	hive_id text not null,
	honey_type text not null,
	harvest_date date not null,
	quantity numeric not null,
	status text not null,
	constraint honey_batches_pkey primary key (batch_id),
	constraint honey_batches_hive_id_fkey foreign KEY (hive_id) references hives (hive_id)
) TABLESPACE pg_default;
```

Honey batch records must use this table to provide the batch ID, source hive,
honey type, exact harvest date, and quantity.

### `public.blockchain_blocks`

```sql
create table public.blockchain_blocks (
	batch_id text null,
	event_type text not null,
	timestamp timestamp with time zone null default now(),
	data_hash text not null,
	previous_hash text null,
	block_hash text not null,
	constraint blockchain_blocks_batch_id_fkey foreign KEY (batch_id) references honey_batches (batch_id)
) TABLESPACE pg_default;
```

When a honey jar is scanned through its QR code, use the QR code's `batch_id` to
fetch the matching `public.honey_batches` record and display its batch details.
Provide a **Trace back** action that retrieves the complete history from
`public.blockchain_blocks` for that `batch_id`, ordered from the earliest block
to the latest block.

Blockchain verification must perform both checks below:

1. Recalculate the data hash from the current database data for the batch and
	 compare it with the latest matching block's `data_hash`. If they differ,
	 report that the batch data has been tampered with.
2. Traverse the matching blocks in chronological order. For every block after
	 the first, compare its `previous_hash` with the preceding block's
	 `block_hash`. If they differ, report that the blockchain history has been
	 tampered with.

The QR result and trace-back view must clearly show whether the batch data and
its blockchain history passed or failed verification. Never silently treat a
failed verification as valid.

Endpoints:

- `GET /api/health` checks that the API is running.
- `POST /api/honey-batches` creates a harvested batch for a beekeeper's hive.
- `GET /api/honey-batches` lists batches belonging to the logged-in beekeeper.
- `PATCH /api/honey-batches/{batch_id}` advances a batch from `HARVESTED` to
  `PROCESSED` or from `PROCESSED` to `DISTRIBUTED`.
- `GET /api/auth/config` returns only the public browser configuration.
- `GET /api/auth/session` validates a Supabase access token sent as a Bearer token.
