/**
 * src/pages/ExecutiveOverview.jsx
 *
 * Integrates ALL KPIs from /api/summary and /api/funnel into
 * clearly labelled sections:
 *
 *  1. Core Funnel          — uploaded / generated / published + rates
 *  2. AI Efficiency        — multiplier, compute cost, efficiency score
 *  3. Duration             — compute hours, published hours
 *  4. Channel Health       — best channel, dead channels, active ratio
 *  5. User Highlights      — top user, best efficiency user, zero-value users
 *  6. Language Intelligence — EN vs HI publish rates, efficacy multiplier
 *  7. Monthly Benchmarks   — averages, peak workload, peak value month
 *  8. Platform             — YouTube workload
 *  9. Data Quality         — unknown team attribution %
 * 10. Trend Charts         — 6 charts with explicit pixel heights (no height="100%")
 */

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { KpiCard } from "@/components/kpi-cards/KpiCard";
import { motion } from "framer-motion";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, BarChart, Bar, ScatterChart, Scatter,
} from "recharts";
import {
  UploadCloud, Settings, FileCheck, Percent, Clock, XCircle,
  Zap, TrendingUp, TrendingDown, Users, Radio, Globe,
  Calendar, Star, AlertTriangle, Award, BarChart2, Target,
} from "lucide-react";

// ─────────────────────────────────────────────────────────────────────────────
// CONFIG
// ─────────────────────────────────────────────────────────────────────────────

const API = "http://localhost:8000";

// Hardcoded hex colors — CSS vars don't work inside SVG in all browsers
const C = {
  blue: "#06b6d4",
  green: "#22c55e",
  red: "#ef4444",
  orange: "#f59e0b",
  purple: "#8b5cf6",
  indigo: "#6366f1",
  teal: "#14b8a6",
};

const TT = {
  contentStyle: {
    background: "#1a1b1e", border: "1px solid #333",
    borderRadius: 8, fontSize: 11, color: "#e0e0e0",
  },
};
const AX = {
  tick: { fontSize: 10, fill: "#888" },
  axisLine: { stroke: "#333" },
  tickLine: false,
};

// ─────────────────────────────────────────────────────────────────────────────
// FETCH HELPER
// ─────────────────────────────────────────────────────────────────────────────

async function get(path, fallback) {
  try {
    const r = await fetch(API + path);
    if (!r.ok) { console.warn(`[EO] ${path} → ${r.status}`); return fallback; }
    const d = await r.json();
    if (Array.isArray(d)) return d;
    if (Array.isArray(d?.data)) return d.data;
    return d;
  } catch (e) {
    console.error(`[EO] ${path} failed:`, e.message);
    return fallback;
  }
}

const n = (v) => Number(v ?? 0);
const f1 = (v) => n(v).toFixed(1);
const f2 = (v) => n(v).toFixed(2);
const pf = (v, dp = 1) => parseFloat(n(v).toFixed(dp));

// ─────────────────────────────────────────────────────────────────────────────
// PAGE
// ─────────────────────────────────────────────────────────────────────────────

export default function ExecutiveOverview() {

  const { data: summary = {} } = useQuery({ queryKey: ["summary"], queryFn: () => get("/api/summary", {}), staleTime: 60000 });
  const { data: monthly = [] } = useQuery({ queryKey: ["monthly"], queryFn: () => get("/api/monthly", []), staleTime: 60000 });
  const { data: users = [] } = useQuery({ queryKey: ["users200"], queryFn: () => get("/api/users?limit=200", []), staleTime: 60000 });
  const { data: channels = [] } = useQuery({ queryKey: ["chans"], queryFn: () => get("/api/channels?page_size=100", []), staleTime: 60000 });
  const { data: funnel = null } = useQuery({ queryKey: ["funnel"], queryFn: () => get("/api/funnel", null), staleTime: 60000 });

  const s = summary || {};

  // ── MoM growth helper ──────────────────────────────────────────────────────
  const momPct = (key) => {
    if (monthly.length < 2) return null;
    const c = n(monthly[monthly.length - 1]?.[key]);
    const p = n(monthly[monthly.length - 2]?.[key]);
    return p ? pf((c - p) / p * 100) : null;
  };
  const chg = (key) => {
    const v = momPct(key);
    return v == null ? undefined : `${v >= 0 ? "+" : ""}${v}% MoM`;
  };
  const ct = (key) => (momPct(key) ?? 0) >= 0 ? "up" : "down";

  // ── AI Efficiency composite score ──────────────────────────────────────────
  const aiScore = useMemo(() => {
    const pub = n(s.global_publish_rate);
    const eff = 100 - n(s.ai_compute_waste_rate);
    const mult = Math.min(n(s.ai_content_multiplier) * 20, 100);
    return pf(pub * 0.4 + eff * 0.3 + mult * 0.3);
  }, [s]);

  // ── YouTube hours ──────────────────────────────────────────────────────────
  const ytHours = pf(n(s.youtube_workload_secs) / 3600);

  // ── Funnel data ────────────────────────────────────────────────────────────
  const funnelBars = funnel ? [
    { stage: "Uploaded", value: n(funnel.counts?.uploaded), pct: 100 },
    { stage: "Generated", value: n(funnel.counts?.created), pct: pf(n(funnel.rates?.upload_to_create_pct)) },
    { stage: "Published", value: n(funnel.counts?.published), pct: pf(n(funnel.rates?.create_to_publish_pct)) },
  ] : [
    { stage: "Uploaded", value: n(s.total_uploaded), pct: 100 },
    { stage: "Generated", value: n(s.total_ai_generated_clips), pct: 0 },
    { stage: "Published", value: n(s.total_published_clips), pct: 0 },
  ];

  // ── Chart data — ALL parseFloat, never strings ─────────────────────────────
  const pipelineData = monthly.map(m => ({
    month: String(m.month || "").replace(", ", " "),
    uploaded: n(m.uploaded_count),
    generated: n(m.created_count),
    published: n(m.published_count),
  }));

  const durationData = monthly.map(m => ({
    month: String(m.month || "").replace(", ", " "),
    uploaded: pf(n(m.uploaded_mins) / 60),   // parseFloat — never string
    generated: pf(n(m.created_mins) / 60),
    published: pf(n(m.published_mins) / 60),
  }));

  const publishRateData = monthly.map(m => ({
    month: String(m.month || "").replace(", ", " "),
    rate: pf(n(m.publish_rate), 2),
  }));

  const channelWaste = channels
    .map(c => ({
      name: String(c.channel_name || ""),
      waste: Math.max(0, n(c.created_count) - n(c.published_count)),
      rate: pf(n(c.publish_rate), 1),
    }))
    .sort((a, b) => b.waste - a.waste)
    .slice(0, 12);

  const topUsers = [...users]
    .sort((a, b) => n(b.created_mins) - n(a.created_mins))
    .slice(0, 10)
    .map(u => ({
      name: String(u.user_name || ""),
      compute: pf(n(u.created_mins) / 60),
    }));

  const scatterData = users
    .map(u => ({
      compute: pf(n(u.created_mins) / 60),
      rate: pf(n(u.publish_rate), 1),
      name: String(u.user_name || ""),
    }))
    .filter(d => d.compute > 0);

  // ═══════════════════════════════════════════════════════════════════════════
  // RENDER
  // ═══════════════════════════════════════════════════════════════════════════

  return (
    <DashboardLayout title="Executive Overview">

      {/* ── SECTION 1 : CORE FUNNEL ─────────────────────────────────────── */}
      <SectionLabel icon={BarChart2} label="Core Funnel" color="text-indigo-400" />

      <div className="grid grid-cols-[repeat(auto-fill,minmax(185px,1fr))] gap-3 mb-6">
        <KpiCard title="Uploaded Clips" value={n(s.total_uploaded).toLocaleString()} icon={UploadCloud} change={chg("uploaded_count")} changeType={ct("uploaded_count")} />
        <KpiCard title="AI Generated Clips" value={n(s.total_ai_generated_clips).toLocaleString()} icon={Settings} change={chg("created_count")} changeType={ct("created_count")} />
        <KpiCard title="Published Clips" value={n(s.total_published_clips).toLocaleString()} icon={FileCheck} change={chg("published_count")} changeType={ct("published_count")} />
        <KpiCard title="Publish Rate" value={`${f2(s.global_publish_rate)}%`} icon={Percent} />
        <KpiCard title="Upload→Publish %" value={`${f2(s.upload_to_publish_conv_rate)}%`} icon={TrendingUp} />
        <KpiCard title="Unpublished Gap" value={n(n(s.total_ai_generated_clips) - n(s.total_published_clips)).toLocaleString()} icon={TrendingDown} />
      </div>

      {/* ── SECTION 2 : AI EFFICIENCY ───────────────────────────────────── */}
      <SectionLabel icon={Zap} label="AI Efficiency" color="text-yellow-400" />

      <div className="grid grid-cols-[repeat(auto-fill,minmax(185px,1fr))] gap-3 mb-6">
        <KpiCard title="AI Content Multiplier" value={`${f2(s.ai_content_multiplier)}×`} icon={Zap} />
        <KpiCard title="Compute Waste Rate" value={`${f2(s.ai_compute_waste_rate)}%`} icon={XCircle} />
        <KpiCard title="Avg Clips per Publish" value={`${f2(s.avg_compute_cost_per_pub)}×`} icon={Settings} />
        <KpiCard title="AI Efficiency Score" value={`${aiScore}/100`} icon={Star} />
        <KpiCard title="Create→Publish Rate" value={`${f2(s.global_publish_rate)}%`} icon={Target} />
        <KpiCard title="Create Multiplier" value={`${f2(s.ai_content_multiplier)}×`} icon={TrendingUp} />
      </div>

      {/* ── SECTION 3 : DURATION & COMPUTE ─────────────────────────────── */}
      <SectionLabel icon={Clock} label="Duration & Compute" color="text-cyan-400" />

      <div className="grid grid-cols-[repeat(auto-fill,minmax(185px,1fr))] gap-3 mb-6">
        <KpiCard title="Total Compute Hours" value={`${f1(s.total_server_compute_hrs)} hrs`} icon={Clock} />
        <KpiCard title="Total Published Hours" value={`${f1(s.total_published_hrs)} hrs`} icon={FileCheck} />
        <KpiCard title="YouTube Workload" value={`${f1(ytHours)} hrs`} icon={Radio} />
        <KpiCard title="Avg Monthly Uploads" value={f1(s.avg_monthly_uploads)} icon={UploadCloud} />
        <KpiCard title="Avg Monthly Created" value={f1(s.avg_monthly_created)} icon={Settings} />
        <KpiCard title="Avg Monthly Published" value={f1(s.avg_monthly_published)} icon={FileCheck} />
      </div>

      {/* ── SECTION 4 : CHANNEL HEALTH ──────────────────────────────────── */}
      <SectionLabel icon={Radio} label="Channel Health" color="text-green-400" />

      <div className="grid grid-cols-[repeat(auto-fill,minmax(185px,1fr))] gap-3 mb-6">
        <KpiCard title="Best Channel" value={String(s.best_channel_name || "—")} icon={Award} />
        <KpiCard title="Best Channel Pub Rate" value={`${f2(s.best_channel_publish_rate)}%`} icon={Percent} />
        <KpiCard title="Dead Channels %" value={`${f2(s.dead_channel_pct)}%`} icon={TrendingDown} />
        <KpiCard title="Active Channel Ratio" value={`${f2(s.active_channel_ratio)}%`} icon={TrendingUp} />
        <KpiCard title="Ch A Contribution" value={`${f2(s.ch_a_contribution_pct)}%`} icon={BarChart2} />
        <KpiCard title="Zero Value Users" value={String(n(s.zero_value_users))} icon={Users} />
      </div>

      {/* ── SECTION 5 : USER HIGHLIGHTS ─────────────────────────────────── */}
      <SectionLabel icon={Users} label="User Highlights" color="text-purple-400" />

      <div className="grid grid-cols-[repeat(auto-fill,minmax(185px,1fr))] gap-3 mb-6">
        <KpiCard title="Top Volume User" value={String(s.top_volume_user || "—")} icon={Users} />
        <KpiCard title="Best Efficiency User" value={String(s.best_efficiency_user || "—")} icon={Star} />
        <KpiCard title="Best User Pub Rate" value={`${f2(s.best_efficiency_pub_rate)}%`} icon={Percent} />
        <KpiCard title="Zero Value Users" value={String(n(s.zero_value_users))} icon={AlertTriangle} />
        <KpiCard title="Avg Monthly Uploads" value={f1(s.avg_monthly_uploads)} icon={UploadCloud} />
        <KpiCard title="Avg Monthly Published" value={f1(s.avg_monthly_published)} icon={FileCheck} />
      </div>

      {/* ── SECTION 6 : LANGUAGE INTELLIGENCE ──────────────────────────── */}
      <SectionLabel icon={Globe} label="Language Intelligence" color="text-teal-400" />

      <div className="grid grid-cols-[repeat(auto-fill,minmax(185px,1fr))] gap-3 mb-6">
        <KpiCard title="English Publish Rate" value={`${f2(s.en_publish_rate)}%`} icon={Globe} />
        <KpiCard title="Hindi Publish Rate" value={`${f2(s.hi_publish_rate)}%`} icon={Globe} />
        <KpiCard title="EN/HI Efficacy ×" value={`${f2(s.en_hi_efficacy_multiplier)}×`} icon={TrendingUp} />
        <KpiCard title="EN Generation Cost" value={`${f1(s.en_gen_cost)}× per publish`} icon={Settings} />
        <KpiCard title="HI Generation Cost" value={`${f1(s.hi_gen_cost)}× per publish`} icon={Settings} />
        <KpiCard title="Unknown Team %" value={`${f2(s.unknown_team_attribution_pct)}%`} icon={AlertTriangle} />
      </div>

      {/* ── SECTION 7 : MONTHLY BENCHMARKS ─────────────────────────────── */}
      <SectionLabel icon={Calendar} label="Monthly Benchmarks" color="text-orange-400" />

      <div className="grid grid-cols-[repeat(auto-fill,minmax(185px,1fr))] gap-3 mb-6">
        <KpiCard title="Peak Workload Month" value={String(s.peak_workload_month || "—")} icon={Calendar} />
        <KpiCard title="Peak Workload Clips" value={n(s.peak_workload_clips).toLocaleString()} icon={Settings} />
        <KpiCard title="Peak Slice Ratio" value={`${f2(s.peak_slice_ratio)}×`} icon={Zap} />
        <KpiCard title="Peak Value Month" value={String(s.peak_value_month || "—")} icon={Star} />
        <KpiCard title="Peak Published Clips" value={n(s.peak_value_pub_count).toLocaleString()} icon={FileCheck} />
        <KpiCard title="Dec→Feb Upload Surge" value={`${f1(s.dec_to_feb_upload_surge_pct)}%`} icon={TrendingUp} />
      </div>

      {/* ── FUNNEL VISUAL + WASTE PANEL ─────────────────────────────────── */}
      <SectionLabel icon={Target} label="Funnel & Waste" color="text-red-400" />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">

        {/* Funnel chart */}
        <ChartCard title="AI Pipeline Funnel">
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={funnelBars} layout="vertical">
              <XAxis type="number" {...AX} />
              <YAxis type="category" dataKey="stage" {...AX} width={75} />
              <Tooltip {...TT} />
              <Bar dataKey="value" fill={C.indigo} radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        {/* Waste chart */}
        <ChartCard title="Published vs Wasted Clips">
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={[
              { name: "Published", value: n(s.total_published_clips) },
              { name: "Wasted", value: Math.max(0, n(s.total_ai_generated_clips) - n(s.total_published_clips)) },
            ]}>
              <XAxis dataKey="name" {...AX} />
              <YAxis {...AX} />
              <Tooltip {...TT} />
              <Bar dataKey="value" fill={C.orange} radius={4} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        {/* Funnel drop-off stats */}
        <div className="rounded-xl border bg-card p-5">
          <h3 className="mb-4 text-sm font-semibold">Funnel Drop-off</h3>
          <div className="space-y-3">
            {[
              { label: "Upload → Generate", pct: funnel?.rates?.upload_to_create_pct, color: C.blue, icon: "📤" },
              { label: "Generate → Publish", pct: funnel?.rates?.create_to_publish_pct, color: C.green, icon: "🚀" },
              { label: "Upload → Publish", pct: funnel?.rates?.upload_to_publish_pct, color: C.indigo, icon: "✅" },
              { label: "Drop-off Rate", pct: funnel?.rates?.drop_off_pct, color: C.red, icon: "⚠️" },
            ].map(({ label, pct, color, icon }) => (
              <div key={label} className="flex items-center justify-between">
                <span className="text-xs text-muted-foreground">{icon} {label}</span>
                <div className="flex items-center gap-2">
                  <div className="w-20 h-1.5 rounded-full bg-muted overflow-hidden">
                    <div className="h-full rounded-full" style={{ width: `${Math.min(n(pct), 100)}%`, background: color }} />
                  </div>
                  <span className="text-xs font-semibold w-12 text-right"
                    style={{ color }}>
                    {pf(n(pct), 1)}%
                  </span>
                </div>
              </div>
            ))}

            <div className="mt-4 pt-3 border-t border-border space-y-2">
              <StatRow label="Compute waste rate" value={`${f2(s.ai_compute_waste_rate)}%`} />
              <StatRow label="Clips per publish" value={`${f1(s.avg_compute_cost_per_pub)} clips`} />
              <StatRow label="AI multiplier" value={`${f2(s.ai_content_multiplier)}×`} />
            </div>
          </div>
        </div>

      </div>

      {/* ── KEY INSIGHTS ────────────────────────────────────────────────── */}

      {/* ── SECTION 8 : TREND CHARTS ────────────────────────────────────── */}
      <SectionLabel icon={TrendingUp} label="Trend Charts" color="text-blue-400" />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">

        <ChartCard title="Pipeline Trend (Uploaded / Generated / Published)">
          {pipelineData.length === 0
            ? <NoData />
            : <ResponsiveContainer width="100%" height={260}>
              <LineChart data={pipelineData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a2a2a" />
                <XAxis dataKey="month" {...AX} />
                <YAxis {...AX} />
                <Tooltip {...TT} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Line type="monotone" dataKey="uploaded" stroke={C.blue} strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="generated" stroke={C.green} strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="published" stroke={C.indigo} strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          }
        </ChartCard>

        <ChartCard title="Duration Trend (hours)">
          {durationData.length === 0
            ? <NoData />
            : <ResponsiveContainer width="100%" height={260}>
              <LineChart data={durationData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a2a2a" />
                <XAxis dataKey="month" {...AX} />
                <YAxis {...AX} />
                <Tooltip {...TT} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Line type="monotone" dataKey="uploaded" stroke={C.blue} strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="generated" stroke={C.green} strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="published" stroke={C.indigo} strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          }
        </ChartCard>

        <ChartCard title="Publish Rate Trend (%)">
          {publishRateData.length === 0
            ? <NoData />
            : <ResponsiveContainer width="100%" height={260}>
              <LineChart data={publishRateData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a2a2a" />
                <XAxis dataKey="month" {...AX} />
                <YAxis unit="%" {...AX} />
                <Tooltip {...TT} />
                <Line type="monotone" dataKey="rate" stroke={C.indigo} strokeWidth={2} dot={{ r: 3, fill: C.indigo }} />
              </LineChart>
            </ResponsiveContainer>
          }
        </ChartCard>

        <ChartCard title="User Efficiency (Compute hrs vs Publish %)">
          {scatterData.length === 0
            ? <NoData />
            : <ResponsiveContainer width="100%" height={260}>
              <ScatterChart>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a2a2a" />
                <XAxis type="number" dataKey="compute" name="Compute hrs" {...AX} />
                <YAxis type="number" dataKey="rate" name="Publish %"  {...AX} />
                <Tooltip {...TT} cursor={{ strokeDasharray: "3 3" }} />
                <Scatter data={scatterData} fill={C.purple} />
              </ScatterChart>
            </ResponsiveContainer>
          }
        </ChartCard>

        <ChartCard title="Compute Waste by Channel">
          {channelWaste.length === 0
            ? <NoData />
            : <ResponsiveContainer width="100%" height={260}>
              <BarChart data={channelWaste}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a2a2a" />
                <XAxis dataKey="name" {...AX} />
                <YAxis {...AX} />
                <Tooltip {...TT} />
                <Bar dataKey="waste" fill={C.red} radius={[4, 4, 0, 0]} name="Unpublished gap" />
              </BarChart>
            </ResponsiveContainer>
          }
        </ChartCard>

        <ChartCard title="Top 10 Users by Compute Hours">
          {topUsers.length === 0
            ? <NoData />
            : <ResponsiveContainer width="100%" height={260}>
              <BarChart data={topUsers} layout="vertical">
                <XAxis type="number" {...AX} />
                <YAxis type="category" dataKey="name" {...AX} width={85} />
                <Tooltip {...TT} />
                <Bar dataKey="compute" fill={C.green} radius={[0, 4, 4, 0]} name="Compute hrs" />
              </BarChart>
            </ResponsiveContainer>
          }
        </ChartCard>

      </div>

      {/* ── SECTION 9 : AI INSIGHTS ─────────────────────────────────────── */}
      <InsightsSection s={s} funnel={funnel} />

    </DashboardLayout>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// SUB-COMPONENTS
// ─────────────────────────────────────────────────────────────────────────────

function SectionLabel({ icon: Icon, label, color }) {
  return (
    <div className={`flex items-center gap-2 mb-3 mt-2 ${color}`}>
      <Icon className="h-4 w-4" />
      <span className="text-xs font-bold uppercase tracking-widest">{label}</span>
      <div className="flex-1 h-px bg-border/60 ml-1" />
    </div>
  );
}

function ChartCard({ title, children }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="rounded-xl border bg-card p-5"
    >
      <h3 className="mb-3 text-sm font-semibold text-foreground">{title}</h3>
      {children}
    </motion.div>
  );
}

function NoData() {
  return (
    <div className="flex h-[260px] items-center justify-center text-sm text-muted-foreground">
      No data — run ETL pipeline first
    </div>
  );
}

function StatRow({ label, value }) {
  return (
    <div className="flex justify-between text-xs">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-semibold text-foreground">{value}</span>
    </div>
  );
}

// ── AI Insights derived from all KPIs ─────────────────────────────────────────
function InsightsSection({ s, funnel }) {
  const n2 = (v) => Number(v ?? 0);

  const insights = useMemo(() => {
    const list = [];

    const pr = n2(s.global_publish_rate);
    if (pr > 0)
      list.push({
        severity: pr < 2 ? "high" : pr < 5 ? "medium" : "info",
        title: `Global publish rate is ${pr.toFixed(2)}%`,
        detail: `${(100 - pr).toFixed(1)}% of AI-generated clips are never published. ${n2(s.total_ai_generated_clips).toLocaleString() - n2(s.total_published_clips).toLocaleString()} clips represent unused compute.`,
      });

    const mult = n2(s.ai_content_multiplier);
    if (mult > 0)
      list.push({
        severity: "info",
        title: `AI multiplier: ${mult.toFixed(2)}× — each upload generates ${mult.toFixed(1)} clips`,
        detail: `Frammer creates ${mult.toFixed(1)} output clips per uploaded source video. Core product value metric.`,
      });

    const dead = n2(s.dead_channel_pct);
    if (dead > 0)
      list.push({
        severity: dead > 30 ? "high" : "medium",
        title: `${dead.toFixed(0)}% of channels have zero published videos`,
        detail: `These channels consume processing resources but contribute nothing to audience reach. Requires investigation.`,
      });

    const en = n2(s.en_publish_rate), hi = n2(s.hi_publish_rate);
    if (en > 0 && hi > 0)
      list.push({
        severity: hi < 1 ? "medium" : "info",
        title: `English (${en.toFixed(1)}%) publishes ${n2(s.en_hi_efficacy_multiplier).toFixed(1)}× more than Hindi (${hi.toFixed(1)}%)`,
        detail: `Hindi content is heavily processed but rarely published. Workflow or editorial prioritization gap.`,
      });

    const zv = n2(s.zero_value_users);
    if (zv > 0)
      list.push({
        severity: zv > 10 ? "medium" : "info",
        title: `${zv} users have created content but never published anything`,
        detail: `These users add compute cost without contributing to publishing output. May indicate onboarding or workflow gaps.`,
      });

    const unk = n2(s.unknown_team_attribution_pct);
    if (unk > 50)
      list.push({
        severity: "high",
        title: `${unk.toFixed(0)}% of videos have no team attribution`,
        detail: `Team-level analysis is impossible without fixing team name assignment. All team_name values are 'Unknown'.`,
      });

    const peak = s.peak_workload_month;
    if (peak)
      list.push({
        severity: "info",
        title: `Peak workload was ${peak} with ${n2(s.peak_workload_clips).toLocaleString()} clips at ${n2(s.peak_slice_ratio).toFixed(1)}× slice ratio`,
        detail: `${s.peak_value_month || peak} had the highest publishing output: ${n2(s.peak_value_pub_count).toLocaleString()} clips published.`,
      });

    const surge = n2(s.dec_to_feb_upload_surge_pct);
    if (Math.abs(surge) > 10)
      list.push({
        severity: surge > 0 ? "info" : "medium",
        title: `Dec→Feb upload ${surge > 0 ? "surge" : "drop"}: ${surge.toFixed(1)}%`,
        detail: surge > 0
          ? "Upload volume increased significantly from December to February — possible seasonal content drive."
          : "Upload volume dropped from December to February — may indicate reduced content pipeline activity.",
      });

    const best = s.best_channel_name;
    if (best)
      list.push({
        severity: "info",
        title: `Channel ${best} leads with ${n2(s.best_channel_publish_rate).toFixed(1)}% publish rate`,
        detail: `This channel is the benchmark for operational efficiency across the platform.`,
      });

    return list;
  }, [s]);

  if (insights.length === 0) return null;

  return (
    <>
      <SectionLabel icon={AlertTriangle} label="AI Insights" color="text-yellow-400" />
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 mb-6">
        {insights.map((ins, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.04 }}
            className={`p-4 rounded-xl border-l-2 text-xs ${ins.severity === "high"
              ? "border-red-500   bg-red-500/5   text-red-400"
              : ins.severity === "medium"
                ? "border-yellow-500 bg-yellow-500/5 text-yellow-500"
                : "border-blue-500 bg-blue-500/5 text-blue-400"
              }`}
          >
            <p className="font-semibold mb-1 leading-snug">{ins.title}</p>
            <p className="opacity-75 leading-relaxed">{ins.detail}</p>
          </motion.div>
        ))}
      </div>
    </>
  );
}
