# Frammer Analytics — Frontend

A React + Vite analytics dashboard for the Frammer AI content platform. It visualises media production KPIs, usage trends, channel/user performance, multi-dimensional cross-analysis, a searchable video explorer, and an AI chat interface powered by the Frammer backend NLP pipeline.

---

## Tech Stack

| Layer | Library / Tool |
|-------|---------------|
| Framework | React 18 + Vite 8 |
| Routing | React Router DOM v6 |
| Data fetching | TanStack React Query v5 |
| Charts | Recharts + Plotly.js (react-plotly.js) |
| UI components | shadcn/ui (Radix UI primitives) |
| Styling | Tailwind CSS v3 + tailwindcss-animate |
| Animations | Framer Motion |
| Icons | Lucide React |
| Forms | React Hook Form + Zod |
| Testing | Vitest + Testing Library + Playwright |

---

## Project Structure

```
Frontend/
├── public/
│   ├── favicon.ico
│   └── placeholder.svg
│
├── src/
│   ├── main.jsx                          # React DOM entry point
│   ├── App.jsx                           # Router + global providers
│   ├── App.css / index.css               # Global styles + Tailwind base
│   │
│   ├── pages/
│   │   ├── ExecutiveOverview.jsx         # / — KPI dashboard + charts
│   │   ├── UsageTrends.jsx               # /usage — monthly time-series
│   │   ├── ClientAnalysis.jsx            # /clients — channel & user breakdown
│   │   ├── MultiDimensionalAnalysis.jsx  # /multi — cross-dimension heatmaps
│   │   ├── VideoExplorer.jsx             # /explorer — paginated video table
│   │   ├── ChatbotPage.jsx               # /chat — full-page AI chat
│   │   ├── DataQualityPage.jsx           # /data-quality — validation results
│   │   ├── Index.jsx                     # Redirect helper
│   │   └── NotFound.jsx                  # 404 page
│   │
│   ├── components/
│   │   ├── layout/
│   │   │   ├── DashboardLayout.jsx       # Shell: sidebar + header + chatbot
│   │   │   ├── AppSidebar.jsx            # Collapsible left nav
│   │   │   └── Header.jsx                # Sticky top bar: title, clock, KPI ticker, user
│   │   ├── chatbot/
│   │   │   └── Chatbot.jsx               # Floating AI chatbot (compact/half/full)
│   │   ├── filters/
│   │   │   └── GlobalFilterPanel.jsx     # Reusable filter panel component
│   │   ├── kpi-cards/
│   │   │   └── KpiCard.jsx               # Metric card with icon, value, trend
│   │   ├── NavLink.jsx                   # Active-aware router link
│   │   └── ui/                           # shadcn/ui primitives + custom
│   │       ├── AiSearchBar.jsx           # Search input with AI styling
│   │       ├── StatusBadge.jsx           # Published / Not Published badge
│   │       ├── button.jsx, card.jsx,     # Standard shadcn components
│   │       │   input.jsx, select.jsx,
│   │       │   table.jsx, badge.jsx,
│   │       │   avatar.jsx, toast.jsx,
│   │       │   toaster.jsx, sonner.jsx,
│   │       │   tooltip.jsx, sheet.jsx,
│   │       │   sidebar.jsx, skeleton.jsx,
│   │       │   scroll-area.jsx, ...
│   │       └── logo.png
│   │
│   ├── contexts/
│   │   └── FilterContext.jsx             # Global filter state (server-side filtering)
│   │
│   ├── hooks/
│   │   ├── use-mobile.jsx                # Responsive breakpoint hook
│   │   └── use-toast.js                  # Toast notification hook
│   │
│   ├── lib/
│   │   ├── api.js                        # Centralised API client + query functions
│   │   └── utils.js                      # cn() class utility
│   │
│   ├── services/
│   │   └── dataProcessing.js             # Data transformation helpers
│   │
│   ├── data/
│   │   └── mockData.js                   # Static fallback data (dev only)
│   │
│   └── test/
│       ├── setup.js
│       └── example.test.js
│
├── vite.config.js                        # Vite + proxy config
├── tailwind.config.js                    # Tailwind theme
├── components.json                       # shadcn/ui config
├── tsconfig.json / tsconfig.app.json     # TypeScript config
├── package.json
└── index.html
```

---

## Setup & Running

### Prerequisites

- Node.js 18+
- The Frammer backend running at `http://localhost:8000`

### Install

```bash
npm install
```

### Development

```bash
npm run dev
```

Opens at `http://localhost:8080`. All `/api/*` requests are proxied to `http://localhost:8000` automatically via Vite's proxy config — no CORS issues in development.

### Production Build

```bash
npm run build
```

Set the `VITE_API_URL` environment variable to point at the deployed backend:

```bash
VITE_API_URL=https://your-backend.onrender.com npm run build
```

### Preview Built Bundle

```bash
npm run preview
```

### Run Tests

```bash
npm test            # single run
npm run test:watch  # watch mode
```

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `VITE_API_URL` | Backend base URL for production builds | `""` (uses Vite proxy in dev) |

In development, `lib/api.js` falls back to `http://localhost:8000` directly. In production it reads `VITE_API_URL`.

---

## Pages & Routes

### `/` — Executive Overview

The top-level KPI dashboard. Fetches summary, funnel, monthly, channels, users, kpis, and insights data simultaneously via React Query.

**Sections:**
- **Volume KPIs** — uploads, AI-created clips, published clips, active users (3-card grid, expandable to show all with individual insights)
- **Efficiency KPIs** — publish rate, multiplication ratio, unpublished gap, compute waste
- **Pipeline Funnel** — upload → create → publish with drop-off percentages
- **Monthly Trend** — line/bar charts for uploads, created, published over time
- **Channel Performance** — top channels by publish rate, scatter chart
- **User Leaderboard** — top uploaders and most efficient users
- **Pre-computed Insights** — AI-generated textual insights from the backend

Each KPI section shows an inline summary insight next to the heading. Clicking "+ N more KPIs" expands the grid and shows per-card detailed insights. Uses Framer Motion for smooth expand/collapse animation.

---

### `/usage` — Usage & Trends

Monthly time-series analysis with comparison toggles.

**Charts:**
- Upload count over time (with optional previous-month overlay)
- AI-created count over time
- Published count over time
- Processing hours per month
- Upload→Create and Create→Publish conversion rates (%)
- Compute efficiency % (published_mins / created_mins)
- Output type volume bar chart
- Input type created vs published grouped bar
- Language breakdown bar chart
- Statistical anomaly detection (>2σ from mean)

A **"Compare with previous month"** toggle overlays the prior month's line on each trend chart. Anomalous months are flagged with an amber label.

---

### `/clients` — Client Analysis

Channel-by-channel and user-by-user performance breakdown.

**Sections:**
- Summary KPIs: total channels, users, active platforms
- Channel processed vs published bar chart
- Channel publish rates bar chart
- Platform distribution pie chart
- Language created vs published grouped bar
- Top 10 users by upload volume
- Channel efficiency scatter plot (created vs published)
- Full channel summary table with publish rate, gap, upload mins

---

### `/multi` — Multi-Dimensional Analysis

Cross-tabulates two dimensions chosen from a dropdown.

**Available dimension pairs:**
- Channel × User
- Channel × Platform
- User × Input Type
- User × Platform
- User × Published Status
- Input Type × Platform
- Input Type × Published Status

**Visualisations:**
- Stacked bar chart (dim1 entities as bars, dim2 values as stacks)
- Top entities by volume (horizontal bar)
- Publish rate by first dimension (sorted bar)
- Full heatmap (dim1 rows × dim2 columns, coloured by value)

Data is fetched from `/api/multidimensional?dim1=...&dim2=...` and stored as pre-computed cross Parquet files on the backend.

---

### `/explorer` — Video Explorer

Paginated, filterable, searchable table of individual video records.

**Features:**
- Search by headline (server-side, triggers on Enter or Search button)
- Filter by input type (dropdown populated from `/api/input-types`)
- Filter by published status (Published / Not Published)
- 50 videos per page with prev/next pagination
- Total count display
- **CSV export** — fetches all pages at 500/request and downloads a local `.csv`
- Published status shown as a coloured `StatusBadge`
- Clear all filters button

---

### `/chat` — AI Chat (full-page)

A full-page conversational interface to the backend NLP pipeline.

**Features:**
- Starter question tiles (8 suggested prompts)
- POST to `/api/chat` with `{ question, session_id }`
- Session ID persists across turns for multi-turn context; "New Chat" resets it
- Renders per-message: insight text, generated SQL (collapsible), data table (collapsible), Plotly chart (collapsible)
- Handles all agent states: `success`, `needs_input` (amber), `cannot_answer` (yellow suggestions), `error` (red)
- Copy-to-clipboard on code blocks
- Auto-growing textarea (max 120px height)
- Auto-scroll to latest message

---

### `/data-quality` — Data Quality

Displays validation check results from `/api/data-quality/checks`.

**Sections:**
- Summary KPIs: overall quality score, pass/warn/fail counts, last run timestamp
- Quality score bar chart per file (score = 100 − fail×15 − warn×8)
- Per-file expandable cards showing a full check table
- All-checks panel with search by check name/message and filter by status (ALL / PASS / WARN / FAIL)
- Manual refresh button

---

## Shared Layout (DashboardLayout)

Every page is wrapped in `DashboardLayout`, which renders:

1. **AppSidebar** — collapsible icon/full sidebar with 7 navigation items
2. **Header** — sticky top bar containing:
   - Sidebar toggle button
   - Page title with accent bar
   - Live clock (date + time, updates every second)
   - **KPI Ticker** — animates through Uploads / Created / Published MoM values with trend arrows every 5 seconds
   - Notification bell (with red dot badge)
   - User avatar / menu (Frammer AI Admin)
3. **Main content area** — scrollable, with padding
4. **Floating Chatbot** — shown on every page except `/chat` (to avoid duplication)

---

## Floating Chatbot (Chatbot.jsx)

A resizable, page-aware AI assistant available on every dashboard page.

**Size modes** (toggle buttons in chatbot header):
| Mode | Size |
|------|------|
| Compact | 380 × 520 px (bottom-right corner) |
| Half | 50vw × 100vh (right half, full height) |
| Full | 100vw × 100vh (full-screen overlay) |

**Page context awareness:**
The chatbot reads the current route via `useLocation()` and injects a page-specific context hint into every API call. This tells the NLP backend what data the user is currently viewing. Each page has:
- A display label (e.g. "Client Analysis")
- A pre-written context hint with current KPI values
- 4 suggested questions specific to that page

Chat history is **reset automatically** when the user navigates to a different page.

Plotly charts returned by the backend are lazy-loaded and rendered inline within the chat message.

---

## API Client (lib/api.js)

Centralised API layer used by all pages.

```js
import { api } from '@/lib/api';

// Examples
api.summary()                   // GET /api/summary
api.monthly(2025)               // GET /api/monthly?year=2025
api.channels('published_count') // GET /api/channels?sort_by=published_count&order=desc
api.multidim('user', 'platform') // GET /api/multidimensional?dim1=user&dim2=platform
api.videos({ page: 2, search: 'budget', input_type: 'text' })
api.chatStream('top 5 users')   // returns SSE URL string
```

`apiFetch()` throws descriptive errors on non-2xx responses. `extractArray()` safely unpacks both plain-array and paginated `{ data: [] }` responses.

---

## Filter Context (contexts/FilterContext.jsx)

Global React context providing filter state across pages. All filtering is **server-side** — the context holds the filter values and `toVideoParams()` converts them to API query params.

```js
const { filters, updateFilter, clearFilters, activeCount, toVideoParams } = useFilters();
```

Available filter keys: `search`, `inputType`, `outputType`, `language`, `platform`, `publishedStatus`.

---

## Key Design Decisions

- **Dark-first theme** — all charts use a dark tooltip style (`#1a1b1e` background), dark axis ticks (`#888`), and a consistent colour palette: `#06b6d4` (cyan), `#22c55e` (green), `#ef4444` (red), `#f59e0b` (amber), `#8b5cf6` (purple), `#6366f1` (indigo).
- **No client-side filtering** — all filtering and pagination happens on the backend. The frontend passes params to the API and displays results.
- **React Query caching** — all queries use a 60-second stale time. No refetch on window focus. Single retry on failure.
- **Framer Motion** — used for card reveal animations (`opacity: 0 → 1, y: 6 → 0`), section expand/collapse (`AnimatePresence`), and KPI ticker transitions.
- **Plotly for NLP charts** — backend returns PNG chart URLs for the full chat page. The floating chatbot lazy-loads `react-plotly.js` only when needed.
- **Session isolation** — each chat session gets a `crypto.randomUUID()` session ID, sent with every message so the backend NLP agent can maintain multi-turn context without bleed-through between users.

---

## Deployment

The frontend is a static SPA. Build and serve the `dist/` folder from any static host (Netlify, Vercel, Render static site, S3+CloudFront, etc.).

Set `VITE_API_URL` to your backend URL at build time:

```bash
VITE_API_URL=https://frammer-backend.onrender.com npm run build
```

Ensure the backend has `Access-Control-Allow-Origin: *` (or your frontend domain) in its CORS config — this is already set in the FastAPI backend with `allow_origins=["*"]`.