# Frammer Analytics — Backend

A production-grade analytics API for the Frammer AI content platform. It ingests raw CSV exports, runs a multi-step ETL pipeline into DuckDB, exposes a FastAPI REST layer, and answers natural language questions using a Gemini-powered NLP agent with ChromaDB retrieval.

---

## Architecture

```
Raw CSVs (data/raw/)
      │
      ▼
 ETL Pipeline
  ├── Ingestion  (hash-checked, incremental)
  ├── Validation (PASS / WARN / FAIL)
  └── Transform  (star schema → Parquet → DuckDB)
      │
      ▼
DuckDB + Parquet files (data/processed/)
      │
      ▼
FastAPI (api/main.py)
  ├── /api/analytics      → pre-computed dashboards
  ├── /api/kpis           → north-star + guardian KPIs
  ├── /api/etl            → pipeline triggers & status
  ├── /api/chat           → NLP natural-language queries
  └── /api/data-quality   → data quality reports
      │
      ▼
NLP Layer (nlp_frammer/)
  ├── ChromaDB vector retrieval
  ├── LangGraph agent (SQL generation + execution)
  ├── Gemini synthesis (insight generation)
  └── Plotly chart generation (PNG, saved to data/charts/)
```

The server also runs a **file watcher** (watchdog) on `data/raw/`. When any configured CSV is saved or replaced, the full ETL pipeline re-runs automatically within ~3 seconds — no manual trigger needed.

---

## Project Structure

```
backend/
├── api/
│   ├── main.py                  # FastAPI app, middleware, startup, file watcher
│   └── routes/
│       ├── analytics.py         # All read-only dashboard endpoints
│       ├── chat.py              # NLP chat (JSON + SSE streaming)
│       ├── data_quality.py      # Data quality report endpoints
│       ├── etl.py               # ETL trigger & status endpoints
│       └── kpis.py              # North-star + guardian KPI endpoint
│
├── etl/
│   ├── main.py                  # Full pipeline entry point
│   ├── ingestion/               # CSV → DuckDB (hash-tracked, incremental)
│   ├── validation.py            # PASS/WARN/FAIL data checks
│   ├── transform.py             # Star schema builder + Parquet writer
│   └── cross_parquet.py         # Cross-dimension Parquet files
│
├── nlp_frammer/
│   ├── nlp/
│   │   ├── engine.py            # Public entry point: query() / query_stream()
│   │   ├── agent.py             # LangGraph agent (SQL gen → execute → synthesise)
│   │   ├── retriever.py         # ChromaDB vector store retrieval
│   │   ├── prompt_builder.py    # Schema-aware prompt construction
│   │   ├── executor.py          # DuckDB SQL executor
│   │   ├── synthesiser.py       # Gemini insight generation
│   │   ├── chart_generator.py   # Plotly chart generation → PNG
│   │   ├── metrics.py           # Metric definitions for the NLP layer
│   │   ├── metadata.py          # Table/column metadata for retrieval
│   │   ├── vector_store.py      # ChromaDB index management
│   │   └── examples.py          # Few-shot SQL examples
│   ├── scripts/
│   │   └── build_index.py       # One-time ChromaDB index builder
│   └── requirements.txt         # NLP-specific dependencies
│
├── data/
│   ├── raw/                     # Drop CSV files here (watched for changes)
│   ├── processed/               # Auto-generated Parquet files
│   └── charts/                  # Auto-generated chart PNGs
│
├── config.py                    # Central config: paths, CSV map, KPI defs, QA filters
├── registry.db                  # SQLite file-hash registry (ETL deduplication)
├── requirements.txt             # Core Python dependencies
├── render.yaml                  # Render.com deployment config
└── start.sh                     # Bootstrap script (install deps + start server)
```

---

## Setup

### Prerequisites

- Python 3.12+
- A Gemini API key (for the NLP layer)
- (Optional) An OpenAI API key

### 1. Install dependencies

```bash
pip install -r requirements.txt
pip install -r nlp_frammer/requirements.txt
```

### 2. Configure environment

Create a `.env` file in the `backend/` root:

```env
GEMINI_API_KEY=your_gemini_api_key_here
OPENAI_API_KEY=your_openai_api_key_here   # optional
DATABASE_PATH=database/duckdb.db
DATA_PATH=data/raw
API_PORT=8000
PORT=10000
ENV=production
```

### 3. Place CSV files

Drop your raw CSV exports into `data/raw/`. The expected filenames are defined in `config.py` under `CSV_FILES`:

| Key | Expected filename |
|-----|-------------------|
| `users` | `combined_data(2025-3-1-2026-2-28) by user.csv` |
| `channels` | `CLIENT 1 combined_data(2025-3-1-2026-2-28).csv` |
| `channel_user` | `combined_data(2025-3-1-2026-2-28) by channel and user.csv` |
| `input_types` | `combined_data(2025-3-1-2026-2-28) by input type.csv` |
| `output_types` | `combined_data(2025-3-1-2026-2-28) by output type.csv` |
| `languages` | `combined_data(2025-3-1-2026-2-28) by language.csv` |
| `monthly` | `monthly-chart.csv` |
| `video_list` | `video_list_data_obfuscated.csv` |

### 4. Build the ChromaDB vector index (one-time)

```bash
cd nlp_frammer
python scripts/build_index.py
```

### 5. Run the ETL pipeline

```bash
# Trigger via API after server starts (recommended):
curl -X POST http://localhost:8000/api/etl/run

# Or run directly:
python -m etl.main
```

### 6. Start the server

```bash
# From the backend/ directory:
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

> **Important:** Do **not** use `--reload` with the file watcher active — they conflict on some systems.

Interactive API docs are available at `http://localhost:8000/docs`.

---

## API Endpoints

### Health

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Basic health check + watcher status |
| GET | `/health` | Detailed health: DB tables, Parquet files, row counts |

### Analytics

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/summary` | Overall KPI snapshot |
| GET | `/api/funnel` | Upload → Create → Publish funnel with drop-off rates |
| GET | `/api/users` | Per-user breakdown |
| GET | `/api/channels` | Per-channel breakdown |
| GET | `/api/channels/{name}` | Single-channel drill-down |
| GET | `/api/input-types` | Per-input-type breakdown |
| GET | `/api/output-types` | Per-output-type breakdown |
| GET | `/api/languages` | Per-language breakdown |
| GET | `/api/monthly` | Monthly time-series |
| GET | `/api/publishing-platforms` | Channel × platform cross-table |
| GET | `/api/multidimensional` | Two-dimension cross analysis |
| GET | `/api/dimensions` | List of available dimensions |
| GET | `/api/videos` | Paginated video list with filters |
| GET | `/api/insights` | Pre-computed top insights |
| GET | `/api/data-quality` | Data quality report |

### KPIs

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/kpis` | North-star + guardian KPIs (publish rate, platform coverage, etc.) |

### ETL

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/etl/run?force=false` | Trigger pipeline (incremental by default) |
| GET | `/api/etl/status` | Pipeline status: idle / running / success / failed |

Use `?force=true` to reprocess all files and skip validation failures.

### Chat (NLP)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/chat` | Natural language question → JSON response |
| GET | `/api/chat/stream?question=...` | Same pipeline, SSE streaming for real-time UIs |
| GET | `/api/chat/chart/{chart_id}` | Serve a generated PNG chart |

**POST `/api/chat` request body:**
```json
{
  "question": "Which user uploaded the most videos last month?",
  "session_id": "optional-session-uuid"
}
```

**Response includes:** generated SQL, result rows, a natural language insight, and an optional chart URL.

---

## ETL Pipeline

The pipeline runs in three steps, either triggered via API or automatically when a CSV changes:

1. **Ingestion** — Loads CSVs into DuckDB flat tables. Skips unchanged files using SHA-256 hash tracking (stored in `registry.db`). Pass `force=true` to reprocess all.

2. **Validation** — Runs PASS/WARN/FAIL checks on required columns, null rates, and referential integrity. A FAIL-level result aborts the pipeline unless `force=true`.

3. **Transform** — Cleans data, builds a star schema (`dim_user`, `dim_channel`, `dim_input_type`, `dim_output_type`, `dim_language`, `dim_date`, `fact_video`), writes Parquet files to `data/processed/`, generates cross-dimension Parquets, and computes `summary_stats`.

QA accounts defined in `config.QA_ACCOUNTS` are excluded from all analytics automatically.

---

## NLP Query Pipeline

When a natural language question arrives at `/api/chat`:

1. **Retrieval** — ChromaDB finds relevant table schemas, metric definitions, and few-shot SQL examples.
2. **Prompt building** — A schema-aware prompt is assembled with the retrieved context.
3. **LangGraph agent** — A multi-node graph handles SQL generation → DuckDB execution → Gemini synthesis. Each request gets an isolated `thread_id` to prevent session bleed-through.
4. **Chart generation** — If data is returned, Plotly generates an appropriate chart (bar, line, heatmap, dual-axis) and saves it as a PNG in `data/charts/`.

The streaming endpoint (`/api/chat/stream`) emits SSE events: `sql_ready` → `data_ready` → `insight_ready` → `chart_ready` → `done`.

---

## KPI Definitions

| KPI | Formula |
|-----|---------|
| Publish Rate | `published_count / created_count × 100` |
| Multiplication Ratio | `created_count / uploaded_count` |
| Unpublished Gap | `created_count − published_count` |
| Active Channel Rate | `channels_with_publish / total_channels × 100` |
| MoM Growth | `(current_month − previous_month) / previous_month × 100` |

**North-star metric:** `published_count`  
**Guardian metrics:** `publish_rate`, `platform_coverage`, `team_name_coverage`

---

## Deployment (Render.com)

The `render.yaml` file configures a web service:

```yaml
startCommand: uvicorn api.main:app --host 0.0.0.0 --port 10000
```

Set `PORT=10000` and all API keys as environment variables in the Render dashboard. The `start.sh` script can also be used as the start command for other platforms.

---

## Dependencies

**Core (`requirements.txt`):**
`fastapi`, `uvicorn`, `duckdb`, `pandas`, `numpy`, `pydantic`, `python-dotenv`, `watchdog`, `sqlalchemy`, `langchain`, `openai`, `faiss-cpu`, `sentence-transformers`, `matplotlib`, `seaborn`

**NLP (`nlp_frammer/requirements.txt`):**
`google-genai`, `sentence-transformers`, `chromadb`, `duckdb`, `pandas`, `python-dotenv`, `plotly`, `kaleido`, `langgraph`, `langchain-core`, `langchain-google-genai`
