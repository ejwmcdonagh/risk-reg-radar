# Regulatory Radar

Regulatory Radar watches cybersecurity news from trusted government sources, groups related threats together, and writes intelligence cards a CISO can take straight into a board meeting.

**It is not a compliance checklist. It is a threat intelligence feed that tells you what matters, why it matters, and what to say about it.**

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

You need four things installed on your computer:

- **Python 3.11 or newer** - check by running `python3 --version`
- **Node.js 20 or newer** - check by running `node --version`
- **Docker Desktop** - download from [docker.com](https://www.docker.com/products/docker-desktop)
- **Supabase CLI** - install with `brew install supabase/tap/supabase` on Mac
- **An Anthropic API key** - get one free at [console.anthropic.com](https://console.anthropic.com/keys)

---

## Getting started

### Step 1 - Get the code

```bash
git clone https://github.com/ejwmcdonagh/reg-radar.git
cd reg-radar
```

### Step 2 - Create your config file

```bash
cp backend/.env.example backend/.env
```

Open `backend/.env` in any text editor and fill in your Anthropic API key:

```
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

Leave everything else as it is for now.

### Step 3 - Start the database

Open Docker Desktop first (just launch the app, you don't need to do anything in it).

Then in your terminal:

```bash
supabase start --exclude edge-runtime
```

This starts a local Postgres database. When it finishes you will see a URL and a key. Copy them into `backend/.env`:

```
SUPABASE_URL=http://127.0.0.1:54321
SUPABASE_SERVICE_ROLE_KEY=the-key-shown-in-your-terminal
```

### Step 4 - Run the database setup

```bash
supabase migration up --local
```

This creates the tables the app needs. You only need to do this once.

### Step 5 - Start the backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload
```

Leave this terminal running. The API is now available at `http://localhost:8000`.

### Step 6 - Start the frontend

Open a second terminal window:

```bash
cd frontend
npm install
npm run dev
```

Leave this running too. The dashboard is now at `http://localhost:3000`.

### Step 7 - Load your first data

Open a third terminal window:

```bash
cd backend
source .venv/bin/activate
curl -X POST "http://localhost:8000/api/ingest/run?source=cisa_kev"
curl -X POST "http://localhost:8000/api/ingest/run?source=nvd"
curl -X POST "http://localhost:8000/api/ingest/run?source=cisa_advisory"
curl -X POST "http://localhost:8000/api/ingest/run?source=ncsc"
```

Then generate the intelligence cards:

```bash
curl -X POST http://localhost:8000/api/clusters/run
curl -X POST http://localhost:8000/api/cards/run
```

The second command calls the AI and takes 1-3 minutes. When it finishes, refresh `http://localhost:3000` and you will see cards in all six lanes.

---

## Every day after that

The system runs automatically on a schedule. You do not need to do anything. If you want to force a fresh run:

```bash
curl -X POST http://localhost:8000/api/clusters/run
curl -X POST http://localhost:8000/api/cards/run
```

---

## Customising your feed

Go to `http://localhost:3000` and click **Customize your feed** in the top right.

**Technology stack** - add the vendors and products your organisation uses (e.g. Palo Alto, Microsoft Exchange, Cisco). Cards that mention these will be highlighted and sorted to the top of each lane.

**Custom sources** - add any RSS or Atom feed URL. The system will ingest it daily alongside the built-in sources.

---

## Switching AI models

The system uses Claude Haiku by default. This costs about $0.10 per full pipeline run and is good enough for testing.

When you are ready for production, switch to Claude Opus for higher quality cards. To do this, open these two files and change the model name:

- `backend/app/services/clustering.py` - look for `model="claude-haiku-4-5-20251001"`
- `backend/app/services/card_generator.py` - look for `model="claude-haiku-4-5-20251001"`

Change both to:

```python
model="claude-opus-4-7",
thinking={"type": "adaptive"},
```

Opus costs about $0.50 per full run. Token usage is logged on every card so you can track costs.

---

## Troubleshooting

**"command not found: python"** - use `python3` instead of `python` on Mac.

**SSL certificate errors** - this usually happens on corporate laptops. The app uses `truststore` to read your system certificates automatically. If you still see errors, ask your IT team which certificate file your network uses.

**Docker not running** - open Docker Desktop before running `supabase start`.

**Port already in use** - something else is using port 8000 or 3000. Find and stop the other process, or restart your terminal.

**Cards not appearing** - make sure you ran both `clusters/run` and `cards/run`. Clusters must exist before cards can be generated.

---

## Project structure

```
reg-radar/
├── backend/                  # Python API and pipeline
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
