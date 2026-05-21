# Regulatory Radar

Regulatory Radar watches cybersecurity news from trusted government sources, groups related threats together, and writes intelligence cards a CISO can take straight into a board meeting.

It is not a compliance checklist. It is a threat intelligence feed that tells you what matters, why it matters, and what to say about it.

---

## What problem does it solve?

Security teams are buried in alerts. Most tools just list them. Regulatory Radar reads them, groups the ones that are connected, scores how urgent each group is, and writes a plain-English card for each one.

Each card has five parts:

1. **What is happening** - one sentence, present tense
2. **The evidence** - which sources triggered this card and why
3. **The compliance gap** - which regulation or audit standard this exposes
4. **A question for your team** - something you can ask in a meeting tomorrow
5. **Board talking point** - three sentences a non-technical director can understand

---

## How it works

Every day the system:

1. Pulls threat data from four public sources (CISA, NVD, NCSC)
2. Groups signals that point at the same underlying threat
3. Scores each group by severity, recency, and how many sources agree
4. Writes a card for every group above the score threshold

You can also add your own RSS feeds and tell it which technologies your organisation uses. Cards that mention your tech stack float to the top.

---

## What you need before you start

Install each of these before going any further.

**Python 3.11 or newer**
- Mac: download from [python.org](https://www.python.org/downloads/) or run `brew install python`
- Windows: download from [python.org](https://www.python.org/downloads/) - tick "Add Python to PATH" during install
- Check it worked: open a terminal and type `python3 --version` (Mac) or `python --version` (Windows)

**Node.js 20 or newer**
- Download from [nodejs.org](https://nodejs.org/) - choose the LTS version
- Check it worked: type `node --version` in your terminal

**Docker Desktop**
- Download from [docker.com](https://www.docker.com/products/docker-desktop)
- Install it, then open the app. You will see a whale icon in your menu bar (Mac) or taskbar (Windows). It needs to be running before you start the database in Step 3.

**Supabase CLI**
- Mac: run `brew install supabase/tap/supabase` in your terminal
- Windows: download the latest `supabase_windows_amd64.exe` from [github.com/supabase/cli/releases](https://github.com/supabase/cli/releases), rename it to `supabase.exe`, and move it to a folder that is in your PATH (e.g. `C:\Windows\System32`)

**An Anthropic API key**
- Get one free at [console.anthropic.com/keys](https://console.anthropic.com/keys)
- Keep this somewhere safe. You will need it in Step 2.

---

## Getting started

### Step 1 - Get the code

Open a terminal. On Mac that is the Terminal app. On Windows that is PowerShell (search for it in the Start menu).

```bash
git clone https://github.com/ejwmcdonagh/reg-radar.git
cd reg-radar
```

If you do not have Git installed, download it from [git-scm.com](https://git-scm.com/).

---

### Step 2 - Create your config file

This copies the example config file and creates a real one you can edit.

**Mac:**
```bash
cp backend/.env.example backend/.env
```

**Windows (PowerShell):**
```powershell
Copy-Item backend\.env.example backend\.env
```

Now open `backend/.env` in a text editor. On Mac you can use TextEdit. On Windows you can use Notepad. If you have VS Code installed, run `code backend/.env`.

The file looks like this:

```
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
ANTHROPIC_API_KEY=
...
```

Add your Anthropic API key on the `ANTHROPIC_API_KEY=` line so it looks like:

```
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

Leave everything else blank for now. You will fill in the Supabase values in the next step.

---

### Step 3 - Start the database

Make sure Docker Desktop is open and running first. You should see the whale icon in your menu bar or taskbar.

Then run:

```bash
supabase start --exclude edge-runtime
```

This will take a minute or two the first time. When it finishes you will see output like this:

```
Started supabase local development setup.

         API URL: http://127.0.0.1:54321
          DB URL: postgresql://postgres:postgres@127.0.0.1:54322/postgres
      Studio URL: http://127.0.0.1:54323
    Inbucket URL: http://127.0.0.1:54324
      JWT secret: super-secret-jwt-token-with-at-least-32-characters-long
        anon key: eyJhbGciOiJIUzI1NiIsInR5cCI6...
service_role key: eyJhbGciOiJIUzI1NiIsInR5cCI6...
```

Now open `backend/.env` in your text editor again and fill in these two lines using the values from the output above:

```
SUPABASE_URL=http://127.0.0.1:54321
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6...
```

The `SUPABASE_URL` is always `http://127.0.0.1:54321` when running locally.
The `SUPABASE_SERVICE_ROLE_KEY` is the long `service_role key` value from the output. Copy the whole thing.

Save the file.

---

### Step 4 - Set up the database tables

This creates the tables the app needs. You only need to do this once.

```bash
supabase migration up --local
```

You should see `Local database is up to date.` when it finishes.

---

### Step 5 - Start the backend

Leave Terminal 1 running (with Supabase). Open a new terminal window for this step.

**Mac:**
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload
```

**Windows (PowerShell):**
```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -e .
uvicorn app.main:app --reload
```

When it works you will see `Application startup complete.` in the terminal. Leave this running.

The API is now available at `http://localhost:8000`. You can view the full API docs at `http://localhost:8000/docs`.

---

### Step 6 - Start the frontend

Open a third terminal window. Navigate back to the project root first.

```bash
cd frontend
npm install
npm run dev
```

When it works you will see `Ready in Xms` and a local address. Leave this running.

Open your browser and go to `http://localhost:3000`. You will see an empty dashboard.

---

### Step 7 - Load your first data

Open a fourth terminal window. On Mac, activate the virtual environment first:

```bash
cd backend
source .venv/bin/activate
```

On Windows:
```powershell
cd backend
.venv\Scripts\activate
```

Then run each of these one at a time, waiting for each to finish before running the next:

```bash
curl -X POST "http://localhost:8000/api/ingest/run?source=cisa_kev"
curl -X POST "http://localhost:8000/api/ingest/run?source=nvd"
curl -X POST "http://localhost:8000/api/ingest/run?source=cisa_advisory"
curl -X POST "http://localhost:8000/api/ingest/run?source=ncsc"
```

Each one will return something like `{"inserted": 940}` when done.

Now generate the intelligence clusters and cards:

```bash
curl -X POST http://localhost:8000/api/clusters/run
```

Wait for that to finish, then run:

```bash
curl -X POST http://localhost:8000/api/cards/run
```

This last step calls the AI and takes 1-3 minutes. When it finishes, go back to `http://localhost:3000` and refresh the page. You should see cards in the swim lanes.

---

## Every day after that

The system runs automatically on a daily schedule. You do not need to do anything.

If you want to force a fresh run manually, run these two commands:

```bash
curl -X POST http://localhost:8000/api/clusters/run
curl -X POST http://localhost:8000/api/cards/run
```

---

## Customising your feed

Go to `http://localhost:3000` and click **Customize your feed** in the top right.

**Technology stack** - add the vendors and products your organisation uses (for example: Palo Alto, Microsoft Exchange, Cisco). Cards that mention these will be highlighted and sorted to the top of each lane.

**Custom sources** - add any RSS or Atom feed URL. The system will ingest it daily alongside the built-in sources.

---

## Switching AI models

The system uses Claude Haiku by default. This costs about $0.10 per full pipeline run and is good for testing.

For production, switch to Claude Opus for higher quality cards.

Open these two files in a text editor:
- `backend/app/services/clustering.py`
- `backend/app/services/card_generator.py`

In each file, find the line that says:

```python
model="claude-haiku-4-5-20251001",
```

Change it to:

```python
model="claude-opus-4-7",
thinking={"type": "adaptive"},
```

### Approximate costs per full pipeline run

These are based on a corpus of around 1,000 signals generating roughly 30 cards. Costs scale with corpus size.

| Step | Haiku | Opus |
|------|-------|------|
| Clustering (~150k input tokens) | ~$0.15 | ~$0.75 |
| Card generation (~30 cards) | ~$0.17 | ~$0.87 |
| **Total** | **~$0.33** | **~$1.65** |

Token usage per run is logged in the `metadata.usage` field on every cluster and card row in the database, so you can track actual spend over time.

---

## Troubleshooting

**"command not found: python3"**
On Windows, use `python` instead of `python3`. On Mac, make sure Python is installed from [python.org](https://www.python.org/downloads/).

**"command not found: supabase"**
The Supabase CLI is not installed or not in your PATH. Follow the install instructions in the Prerequisites section above.

**SSL certificate errors when starting the backend**
This usually happens on corporate laptops where the company controls internet traffic. The app uses `truststore` to read your system certificates automatically. If you still see errors, ask your IT team which certificate file your network uses.

**Docker not running**
Open Docker Desktop before running `supabase start`. Wait for the whale icon to appear and stop animating before you proceed.

**"Port already in use"**
Something else is already using port 8000 or 3000. Restart your terminal, or find and stop the other process.

**Cards not appearing on the dashboard**
Make sure you ran both `clusters/run` and `cards/run`. Clusters must exist before cards can be generated. Also check that `ANTHROPIC_API_KEY` is set correctly in `backend/.env`.

**The database command fails with "Cannot find project ref"**
Use `supabase migration up --local` not `supabase db push`. The `db push` command requires a remote Supabase project.

---

## Project structure

```
reg-radar/
├── backend/                  # Python API and data pipeline
│   ├── app/
│   │   ├── ingestion/        # One file per data source
│   │   ├── services/         # Clustering and card generation (AI logic)
│   │   ├── routes/           # API endpoints
│   │   └── ...
│   └── scripts/              # One-off maintenance scripts
├── frontend/                 # Next.js dashboard
│   └── src/
│       ├── app/              # Pages (dashboard, settings)
│       └── components/       # UI components
└── supabase/
    └── migrations/           # Database setup scripts
```

---

## What is built so far

- [x] Step 1 - Pull threat data from CISA, NVD, NCSC
- [x] Step 2 - Group related signals into clusters
- [x] Step 3 - Generate 5-layer intelligence cards using AI
- [x] Step 4 - Dashboard with six domain lanes, card modal, tech stack highlighting
- [ ] Step 5 - Connect to your SIEM or ticketing system
- [ ] Step 6 - Weekly email digest
- [ ] Step 7 - Onboarding flow for new organisations

---

## Licence

MIT
