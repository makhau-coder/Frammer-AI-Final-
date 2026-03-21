# Frammer Analytics

A full-stack product analytics platform for the Frammer AI media operations team. It ingests raw CSV exports from the Frammer platform, processes them through a multi-step ETL pipeline into a DuckDB analytical database, and serves a React dashboard that lets users explore KPIs, usage trends, channel/user performance, and ask natural language questions about the data — answered by a Gemini-powered NLP agent.

---

## Repository Structure

```
frammer_analytics/
├── backend/          # Python — FastAPI + ETL + NLP
└── Frontend/         # React + Vite — Dashboard UI
```

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        DATA SOURCES                             │
│   CSV exports: users · channels · input types · output types   │
│                languages · monthly · video list                 │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      ETL PIPELINE  (backend/etl/)               │
│                                                                 │
│  1. Ingestion ──► SHA-256 hash check ──► DuckDB flat tables     │
│  2. Validation ──► PASS / WARN / FAIL checks                    │
│  3. Transform ──► Star schema + Parquet files                   │
│                                                                 │
│  Auto-triggered by file watcher (watchdog) when CSVs change     │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
        ┌───────────────────┐   ┌───────────────────────┐
        │  DuckDB           │   │  Parquet files        │
        │  (star schema)    │   │  data/processed/      │
        │  dim_user         │   │  users.parquet        │
        │  dim_channel      │   │  channels.parquet     │
        │  dim_input_type   │   │  monthly.parquet      │
        │  dim_language     │   │  cross_*.parquet      │
        │  dim_date         │   │  ...                  │
        │  fact_video       │   └───────────────────────┘
        └───────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FastAPI  (backend/api/)                     │
│                                                                 │
│  /api/summary · /api/funnel · /api/users · /api/channels        │
│  /api/monthly · /api/input-types · /api/output-types            │
│  /api/multidimensional · /api/videos · /api/kpis                │
│  /api/data-quality · /api/etl/run · /api/chat                   │
└───────────────────────────────┬─────────────────────────────────┘
                                │
              ┌─────────────────┴─────────────────┐
              ▼                                   ▼
┌─────────────────────────┐         ┌─────────────────────────────┐
│   NLP Layer             │         │   React Dashboard           │
│   (backend/nlp_frammer/)│         │   (Frontend/)               │
│                         │         │                             │
│  ChromaDB retrieval     │         │  Executive Overview         │
│  LangGraph agent        │         │  Usage & Trends             │
│  Gemini synthesis       │         │  Client Analysis            │
│  DuckDB SQL execution   │         │  Multi-Dimensional Analysis │
│  Plotly chart gen       │         │  Video Explorer             │
│                         │         │  AI Chat                    │
└─────────────────────────┘         │  Data Quality               │
                                    └─────────────────────────────┘
```

---

## Quick Start

### Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.12+ |
| Node.js | 18+ |
| Gemini API Key | Required for NLP chat |

### 1. Clone and set up the backend

```bash
cd backend

# Install dependencies
pip install -r requirements.txt
pip install -r nlp_frammer/requirements.txt

# Configure environment
cp .env.example .env          # then fill in your API keys
# Required: GEMINI_API_KEY
# Optional: OPENAI_API_KEY
```

### 2. Place your CSV data files

Drop your Frammer CSV exports into `backend/data/raw/`. The expected filenames are configured in `backend/config.py`. See the [Backend README](backend/README.md) for the full list.

### 3. Build the NLP vector index (one-time)

```bash
cd backend/nlp_frammer
python scripts/build_index.py
```

### 4. Start the backend

```bash
cd backend
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

The server starts, builds any missing cross-Parquet files, and begins watching `data/raw/` for CSV changes. Run the ETL pipeline to process your CSV data:

```bash
curl -X POST http://localhost:8000/api/etl/run
# Poll status:
curl http://localhost:8000/api/etl/status
```

### 5. Start the frontend

```bash
cd Frontend
npm install
npm run dev
```

Opens at **http://localhost:8080**. All `/api/*` requests are proxied to the backend automatically.

---

## Environment Variables

### Backend (`backend/.env`)

```env
GEMINI_API_KEY=your_gemini_key_here      # Required — NLP chat & synthesis
OPENAI_API_KEY=your_openai_key_here      # Optional
DATABASE_PATH=database/duckdb.db
DATA_PATH=data/raw
API_PORT=8000
PORT=10000                               # Used in production (Render)
ENV=production
```

### Frontend

```env
VITE_API_URL=https://your-backend.onrender.com   # Production only
```

In development, the Vite proxy handles API routing — no `VITE_API_URL` needed.

---

## How It Works

### Data Pipeline

Raw CSV exports land in `backend/data/raw/`. The ETL pipeline runs in three steps:

1. **Ingestion** — Each CSV file is fingerprinted with SHA-256. Only new or changed files are re-loaded into DuckDB flat tables. The file registry (`registry.db`) tracks what has been processed. Pass `force=true` to reprocess everything.

2. **Validation** — Data quality checks run against the loaded tables. Results are graded as PASS, WARN, or FAIL. A FAIL-level result aborts the pipeline unless `force=true` is used. The checks cover null rates, required columns, referential integrity, and duplicate detection.

3. **Transform** — Raw tables are cleaned, QA accounts are excluded, and the data is projected into a star schema in DuckDB (`dim_user`, `dim_channel`, `dim_input_type`, `dim_output_type`, `dim_language`, `dim_date`, `fact_video`). Parquet snapshots are written to `data/processed/` for fast API reads. Cross-dimension Parquet files are also generated for the multi-dimensional analysis page.

The **file watcher** (watchdog) monitors `data/raw/` and automatically re-runs the full pipeline within ~3 seconds whenever a CSV is saved or replaced. No manual trigger needed.

### NLP Chat Pipeline

When a user asks a question via `/api/chat` or the floating chatbot:

1. **Retrieval** — ChromaDB finds relevant table schemas, metric definitions, and few-shot SQL examples based on semantic similarity to the question.
2. **Prompt building** — A schema-aware prompt is assembled with the retrieved context and injected with the page the user is currently viewing.
3. **LangGraph agent** — A multi-node graph handles SQL generation → DuckDB execution → Gemini synthesis. Each session gets an isolated `thread_id` so multi-turn context works without cross-user bleed.
4. **Chart generation** — If rows are returned, Plotly generates an appropriate chart (bar, line, heatmap, dual-axis) and saves it as a PNG in `data/charts/`.
5. **Response** — The API returns the generated SQL, data rows, a natural language insight, and a chart URL (if applicable).

### Frontend Dashboard

The React app has 7 pages served from a collapsible sidebar:

| Page | Route | Description |
|------|-------|-------------|
| Executive Overview | `/` | KPI cards, pipeline funnel, trends, insights |
| Usage & Trends | `/usage` | Monthly time-series, anomaly detection, comparisons |
| Client Analysis | `/clients` | Channel and user performance, platform breakdown |
| Multi-Dimensional | `/multi` | 7 selectable cross-dimension heatmaps |
| Video Explorer | `/explorer` | Searchable, filterable, paginated video table + CSV export |
| AI Chat | `/chat` | Full-page natural language analytics interface |
| Data Quality | `/data-quality` | Validation check results, per-file quality scores |

A **floating AI chatbot** is available on every page (except `/chat`). It reads the current route and automatically injects page-specific context into every query so answers are relevant to what the user is looking at.

The **header KPI ticker** cycles through live upload/created/published month-over-month values every 5 seconds with trend arrows.

---

## Project Details

### Backend

- **Framework:** FastAPI + Uvicorn
- **Database:** DuckDB (analytical), SQLite (file registry)
- **Data format:** Parquet (processed), CSV (raw input)
- **NLP:** LangGraph + LangChain + Google Gemini + ChromaDB
- **Charts:** Plotly (server-side PNG generation)
- **Deployment:** Render.com (`render.yaml` included)

→ See [`backend/README.md`](backend/README.md) for full API reference, ETL details, and deployment guide.

### Frontend

- **Framework:** React 18 + Vite 8
- **Routing:** React Router DOM v6
- **Data fetching:** TanStack React Query v5 (60s cache)
- **Charts:** Recharts + Plotly.js
- **UI:** shadcn/ui (Radix UI) + Tailwind CSS
- **Animations:** Framer Motion

→ See [`Frontend/README.md`](Frontend/README.md) for full page documentation, component guide, and deployment instructions.

---

## Key Design Decisions

**Why DuckDB?**
DuckDB is an in-process analytical database that reads Parquet files natively. It gives SQL query performance on columnar data without needing a separate database server — ideal for a single-tenant analytics backend.

**Why Parquet + DuckDB together?**
The API reads pre-computed Parquet snapshots for fast, repeated dashboard queries (no SQL overhead). DuckDB is used for ad-hoc NLP-generated SQL queries where the schema needs to be queried dynamically.

**Why a file watcher?**
Frammer exports are CSV drops. The watcher means the dashboard automatically stays in sync when new data arrives — no manual ETL trigger or scheduled job needed.

**Why ChromaDB for NLP?**
The NLP layer needs to map a user's freeform question to the right DuckDB tables and columns. ChromaDB stores vector embeddings of table schemas, metric definitions, and example SQL queries. The most relevant context is retrieved and injected into the LLM prompt, keeping the prompt focused and reducing hallucination.

**Why page-context hints in the chatbot?**
Each dashboard page shows different slices of data. Injecting a page hint (e.g. "user is on Client Analysis, showing channel × platform breakdown") lets the NLP agent generate more relevant SQL without the user having to re-explain what they're looking at.

---

## Development Notes

**Running the ETL manually:**
```bash
cd backend
python etl/main.py               # incremental (skip unchanged files)
python etl/main.py --reset       # wipe DB and reprocess everything
python etl/main.py --watch-only  # just run the watcher, skip backfill
```

**Testing the NLP engine interactively:**
```bash
cd backend/nlp_frammer
python main.py                  # standard mode
python main.py --stream         # streaming insight mode
python main.py --debug          # shows retrieved tables + SQL
```

**Verifying config paths:**
```bash
cd backend
python config.py                # prints all paths and CSV file status
```

**Frontend tests:**
```bash
cd Frontend
npm test
```

---

## Deployment

### Backend — Render.com

The `backend/render.yaml` configures a web service. Set the following environment variables in the Render dashboard:

```
GEMINI_API_KEY    → your key
PORT              → 10000
ENV               → production
```

The build command installs dependencies and the start command launches Uvicorn on port 10000.

### Frontend — Static hosting

```bash
cd Frontend
VITE_API_URL=https://your-backend.onrender.com npm run build
```

Deploy the `dist/` folder to Netlify, Vercel, Render static site, or any CDN. The backend already has `allow_origins=["*"]` configured in FastAPI CORS middleware.

---

## Data Model

The star schema built by the ETL pipeline:

```
dim_user          user_id, user_name
dim_channel       channel_id, channel_name
dim_input_type    input_type_id, input_type
dim_output_type   output_type_id, output_type
dim_language      language_id, language
dim_date          date_id, year, month, month_name, quarter

fact_video        video_id, headline, uploaded_by (→ dim_user),
                  input_type (→ dim_input_type),
                  is_published, published_platform, published_url,
                  channel_id (→ dim_channel),
                  language_id (→ dim_language),
                  date_id (→ dim_date), ingested_at
```

**KPI Definitions:**

| Metric | Formula |
|--------|---------|
| Publish Rate | `published_count / created_count × 100` |
| Multiplication Ratio | `created_count / uploaded_count` |
| Unpublished Gap | `created_count − published_count` |
| Active Channel Rate | `channels_with_publish / total_channels × 100` |
| MoM Growth | `(current_month − previous_month) / previous_month × 100` |

**North-star metric:** `published_count`