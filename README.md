# Regulatory Radar

A weekly intelligence agent for CISOs. Monitors real-world threat signals, regulatory updates, and vulnerability data, then surfaces multi-signal provocations in board-ready language that connects genuine cyber risk to commercial consequence.

**This is not a compliance tracker. It is a provocation engine backed by evidence.**

---

## What it does

Most regulatory tracking tools treat all compliance signals equally. Regulatory Radar doesn't.

The agent watches for signal combinations. A breach report alone is noise. A breach report plus a carrier updating their insurance questionnaire plus a new NCSC advisory on the same vector is a provocation worth interrupting a CISO's week for.

Output: **Provocation cards** - structured intelligence cards with 5 layers:
1. Signal headline - what is happening right now
2. Evidence stack - the signals that triggered this card, source attributed
3. Compliance gap - where this falls through the audit landscape
4. Contextual question - "is this true in your organisation?"
5. Board talking point - one paragraph the CISO can use almost verbatim

---

## Architecture

```
regulatory-radar/
├── backend/          # Python / FastAPI - signal ingestion + API
├── frontend/         # Next.js (App Router) - dashboard UI
└── supabase/         # Postgres migrations
    └── migrations/
```

Signal flow:

```
External sources -> Ingesters -> signals table -> (future) combination detector -> provocation cards
```

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11+, FastAPI, APScheduler |
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind CSS |
| Database | Postgres (default: Supabase, see Alternative databases below) |
| HTTP client | httpx (async) |
| Feed parsing | feedparser |

---

## Signal sources (V1)

| Source | Type | Cadence |
|--------|------|---------|
| [CISA KEV](https://www.cisa.gov/known-exploited-vulnerabilities-catalog) | Known Exploited Vulnerabilities catalog | Daily |
| [CISA Advisories](https://www.cisa.gov/cybersecurity-advisories) | Threat advisories (RSS) | Every 6h |
| [NCSC Alerts](https://www.ncsc.gov.uk/section/keep-up-to-date/alerts-advisories) | UK threat alerts (RSS) | Every 6h |
| [NVD CVEs](https://nvd.nist.gov/) | CRITICAL CVEs published in last 30 days | Daily |

---

## Getting started

### Prerequisites

- Python 3.11+
- Node.js 20+
- A Supabase project (free tier works) or see Alternative databases below

### 1. Clone and configure

```bash
git clone https://github.com/ejwmcdonagh/reg-radar.git
cd reg-radar
```

Copy and fill in environment variables:

```bash
cp backend/.env.example backend/.env
```

Required values in `backend/.env`:

```
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
```

Find these in your Supabase project under Settings > API.

### 2. Run the database migration

Option A - Supabase CLI:
```bash
supabase db push
```

Option B - paste directly into the Supabase SQL editor:
```bash
cat supabase/migrations/001_signals.sql
```

### 3. Start the backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload
```

API runs at `http://localhost:8000`. Docs at `http://localhost:8000/docs`.

### 4. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Dashboard runs at `http://localhost:3000`.

---

## API reference

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/signals` | List signals. Query params: `source`, `risk_domain`, `limit`, `offset` |
| `GET` | `/api/signals/stats` | Signal counts by source and domain |
| `GET` | `/api/signals/{id}` | Single signal |
| `POST` | `/api/ingest/run?source={source}` | Trigger a manual ingestion run |
| `GET` | `/api/ingest/status` | Recent ingestion run history |
| `POST` | `/api/clusters/run` | Trigger signal clustering |
| `GET` | `/api/clusters` | List clusters. Query params: `risk_domain`, `status`, `min_score`, `limit`, `offset` |
| `GET` | `/api/clusters/{id}` | Single cluster |
| `POST` | `/api/cards/run` | Trigger provocation card generation |
| `GET` | `/api/cards` | List cards. Query params: `risk_domain`, `status`, `min_score`, `limit`, `offset` |
| `GET` | `/api/cards/{id}` | Single card with all 5 layers |
| `GET` | `/health` | Health check |

Valid `source` values: `cisa_kev`, `cisa_advisory`, `ncsc`, `nvd`

Valid `risk_domain` values: `identity_credential`, `vulnerability_patch`, `supply_chain`, `detection_response`, `data_exposure`, `ransomware_extortion`

### Manual pipeline run (development)

```bash
# Run the full pipeline: ingest all sources, cluster, generate cards
curl -X POST "http://localhost:8000/api/ingest/run?source=cisa_kev"
curl -X POST "http://localhost:8000/api/ingest/run?source=nvd"
curl -X POST "http://localhost:8000/api/clusters/run"
curl -X POST "http://localhost:8000/api/cards/run"

# List the top cards
curl "http://localhost:8000/api/cards" | python3 -m json.tool
```

---

## Alternative databases

The backend uses supabase-py, which talks to Postgres via the [PostgREST](https://postgrest.org/) protocol. You can swap Supabase for any Postgres host by running PostgREST yourself:

1. Deploy PostgREST pointing at your Postgres instance
2. Update `SUPABASE_URL` to your PostgREST endpoint
3. Update `SUPABASE_SERVICE_ROLE_KEY` to your PostgREST JWT secret

The SQL in `supabase/migrations/` is standard Postgres with no Supabase-specific extensions required.

---

## Risk domains

Signals are tagged to one or more domains based on content:

| Domain | What it covers |
|--------|---------------|
| `identity_credential` | Compromised accounts, phishable auth, privilege abuse, NHI sprawl |
| `vulnerability_patch` | Unpatched CVEs, exploit-in-the-wild timing gaps, EOL software |
| `supply_chain` | Vendor compromise, software dependency attacks, third-party access |
| `detection_response` | Dwell time, alert fatigue, logging coverage gaps |
| `data_exposure` | Misconfigured storage, excessive access, exfiltration vectors |
| `ransomware_extortion` | Cross-domain worst-case lens that maps to board and insurer mental model |

Domain mapping logic lives in `backend/app/domain_mapper.py` and is keyword-based in V1. This will be replaced with LLM-assisted classification once there is sufficient signal volume to evaluate quality.

---

## Build sequence

- [x] **Step 1** - Signal ingestion layer
- [x] **Step 2** - Signal combination detection logic
- [x] **Step 3** - Provocation card generator (prompt engineering)
- [ ] **Step 4** - Dashboard shell (domain swim-lane layout)
- [ ] **Step 5** - MCP integration (SIEM + ticketing aggregation)
- [ ] **Step 6** - Email digest renderer
- [ ] **Step 7** - Onboarding flow

---

## LLM model configuration

Two pipeline steps call the Anthropic API: clustering (`backend/app/services/clustering.py`) and card generation (`backend/app/services/card_generator.py`). Both default to `claude-haiku-4-5-20251001` for cost-efficient testing.

### Switching models

**To use Haiku (testing, low cost):**

Both files are already configured for Haiku. No changes needed.

**To use Opus (production quality):**

In `clustering.py` around line 168 and `card_generator.py` around line 127, change:

```python
# Haiku (current default)
model="claude-haiku-4-5-20251001",
max_tokens=4096,
```

to:

```python
# Opus — add thinking for better cluster quality
model="claude-opus-4-7",
max_tokens=4096,
thinking={"type": "adaptive"},
```

Note: `thinking` is not supported on Haiku. Remove it when switching back.

### Approximate costs per pipeline run

| Model | Clustering (~15k input tokens) | Card generation (~2k tokens x 10 cards) |
|-------|-------------------------------|----------------------------------------|
| Haiku | ~$0.015 | ~$0.02 |
| Opus | ~$0.075 | ~$0.10 |

Costs are estimates based on a 1,000 signal corpus. Token usage per run is logged in `metadata.usage` on each cluster and card row.

---

## Contributing

Pull requests welcome. For significant changes, open an issue first to discuss the approach.

---

## Licence

MIT
