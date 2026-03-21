/**
 * ExecutiveOverview.jsx
 *
 * Layout:
 *  - Each section shows 2 KPI cards in a row by default (so right side is NOT empty)
 *  - A concise insight sits to the right of each section heading
 *  - Clicking "+N more KPIs with insights" appends the remaining cards to the same grid
 *    (they appear below the initial 2, expanding the grid downward)
 *  - When expanded, each card shows its own detailed insight beneath it
 *  - The heading insight disappears while expanded (returns when collapsed)
 */

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { KpiCard } from "@/components/kpi-cards/KpiCard";
import { motion, AnimatePresence } from "framer-motion";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, BarChart, Bar, ScatterChart, Scatter,
} from "recharts";
import {
  UploadCloud, Settings, FileCheck, Percent, Clock, XCircle,
  Zap, TrendingUp, TrendingDown, Users, Radio, Globe,
  Calendar, Star, AlertTriangle, Award, BarChart2, Target,
  ChevronDown, ChevronUp, Lightbulb,
} from "lucide-react";
import { BASE_URL } from "@/lib/api";

const API = BASE_URL || "http://localhost:8000";

const C = {
  blue: "#06b6d4", green: "#22c55e", red: "#ef4444",
  orange: "#f59e0b", purple: "#8b5cf6", indigo: "#6366f1", teal: "#14b8a6",
};
const TT = {
  contentStyle: { background: "#1a1b1e", border: "1px solid #333", borderRadius: 8, fontSize: 11, color: "#e0e0e0" },
};
const AX = { tick: { fontSize: 10, fill: "#888" }, axisLine: { stroke: "#333" }, tickLine: false };

async function get(path, fallback) {
  try {
    const r = await fetch(API + path);
    if (!r.ok) return fallback;
    const d = await r.json();
    if (Array.isArray(d)) return d;
    if (Array.isArray(d?.data)) return d.data;
    return d;
  } catch { return fallback; }
}

const n  = (v) => Number(v ?? 0);
const f1 = (v) => n(v).toFixed(1);
const f2 = (v) => n(v).toFixed(2);
const pf = (v, dp = 1) => parseFloat(n(v).toFixed(dp));

// ─────────────────────────────────────────────────────────────────────────────
// KPI SECTION COMPONENT
//
// Behaviour:
//  • Default: shows first `previewCount` (3) cards in a 3-col grid
//  • headingInsight shown inline to the right of the label (disappears on expand)
//  • "+N more" button appends remaining cards to the SAME grid (no separate panel)
//  • Expanded cards each show their own detailed insight below them
// ─────────────────────────────────────────────────────────────────────────────
function KpiSection({ icon: Icon, label, color, cards, previewCount = 3, headingInsight }) {
  const [expanded, setExpanded] = useState(false);
  const hiddenN = cards.length - previewCount;

  return (
    <div className="mb-6">

      {/* Section heading: Icon | LABEL | ──── | inline insight (fades out on expand) | ──── */}
      <div className={`flex items-center gap-2 mb-3 mt-2 ${color}`}>
        <Icon className="h-4 w-4 shrink-0" />
        <span className="text-xs font-bold uppercase tracking-widest whitespace-nowrap">{label}</span>
        <div className="h-px bg-border/60 w-2 shrink-0" />
        <AnimatePresence mode="wait">
          {!expanded && headingInsight && (
            <motion.span
              key="hi"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="flex items-center gap-1 text-[11px] text-muted-foreground font-normal normal-case tracking-normal overflow-hidden"
            >
              <Lightbulb className="h-3 w-3 shrink-0 text-yellow-400" />
              <span className="truncate max-w-[480px]">{headingInsight}</span>
            </motion.span>
          )}
        </AnimatePresence>
        <div className="flex-1 h-px bg-border/60 min-w-[8px]" />
      </div>

      {/* Unified grid — preview cards always present, extras appended when expanded */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {/* Always-visible preview cards */}
        {cards.slice(0, previewCount).map((card, i) => (
          <motion.div key={card.title}
            initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.04 }}>
            <KpiCard {...card} />
          </motion.div>
        ))}

        {/* Extra cards — appended into the same grid when expanded */}
        <AnimatePresence>
          {expanded && cards.slice(previewCount).map((card, i) => (
            <motion.div key={card.title}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 8 }}
              transition={{ delay: i * 0.04 }}>
              <KpiCard {...card} />
              {card.insight && (
                <div className="mt-1 px-3 py-2 rounded-lg bg-muted/30 border border-border/40 text-[10px] text-muted-foreground leading-relaxed flex gap-1.5">
                  <Lightbulb className="h-3 w-3 shrink-0 mt-0.5 text-yellow-400" />
                  <span>{card.insight}</span>
                </div>
              )}
            </motion.div>
          ))}
        </AnimatePresence>
      </div>

      {/* Toggle button */}
      {hiddenN > 0 && (
        <button
          onClick={() => setExpanded(v => !v)}
          className="mt-3 flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          {expanded
            ? <><ChevronUp   className="h-3.5 w-3.5" />Show less</>
            : <><ChevronDown className="h-3.5 w-3.5" />+{hiddenN} more KPIs with insights</>}
        </button>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// PAGE
// ─────────────────────────────────────────────────────────────────────────────
export default function ExecutiveOverview() {

  const { data: summary  = {} } = useQuery({ queryKey: ["summary"],  queryFn: () => get("/api/summary", {}),                staleTime: 60000 });
  const { data: monthly  = [] } = useQuery({ queryKey: ["monthly"],  queryFn: () => get("/api/monthly", []),                staleTime: 60000 });
  const { data: users    = [] } = useQuery({ queryKey: ["users200"], queryFn: () => get("/api/users?limit=200", []),        staleTime: 60000 });
  const { data: channels = [] } = useQuery({ queryKey: ["chans"],    queryFn: () => get("/api/channels?page_size=100", []), staleTime: 60000 });
  const { data: funnel   = null}= useQuery({ queryKey: ["funnel"],   queryFn: () => get("/api/funnel", null),               staleTime: 60000 });

  const s = summary || {};

  const momPct = (key) => {
    if (monthly.length < 2) return null;
    const c = n(monthly[monthly.length - 1]?.[key]);
    const p = n(monthly[monthly.length - 2]?.[key]);
    return p ? pf((c - p) / p * 100) : null;
  };
  const chg = (key) => { const v = momPct(key); return v == null ? undefined : `${v >= 0 ? "+" : ""}${v}% MoM`; };
  const ct  = (key) => (momPct(key) ?? 0) >= 0 ? "up" : "down";

  const aiScore = useMemo(() => {
    const pub  = n(s.global_publish_rate);
    const eff  = 100 - n(s.ai_compute_waste_rate);
    const mult = Math.min(n(s.ai_content_multiplier) * 20, 100);
    return pf(pub * 0.4 + eff * 0.3 + mult * 0.3);
  }, [s]);

  const ytHours = pf(n(s.youtube_workload_secs) / 3600);

  const funnelBars = funnel ? [
    { stage: "Uploaded",  value: n(funnel.counts?.uploaded) },
    { stage: "Generated", value: n(funnel.counts?.created) },
    { stage: "Published", value: n(funnel.counts?.published) },
  ] : [
    { stage: "Uploaded",  value: n(s.total_uploaded) },
    { stage: "Generated", value: n(s.total_ai_generated_clips) },
    { stage: "Published", value: n(s.total_published_clips) },
  ];

  const pipelineData = monthly.map(m => ({
    month: String(m.month || "").replace(", ", " "),
    uploaded: n(m.uploaded_count), generated: n(m.created_count), published: n(m.published_count),
  }));
  const durationData = monthly.map(m => ({
    month: String(m.month || "").replace(", ", " "),
    uploaded: pf(n(m.uploaded_mins) / 60), generated: pf(n(m.created_mins) / 60), published: pf(n(m.published_mins) / 60),
  }));
  const publishRateData = monthly.map(m => ({
    month: String(m.month || "").replace(", ", " "),
    rate: pf(n(m.publish_rate), 2),
  }));
  const channelWaste = channels
    .map(c => ({ name: String(c.channel_name || ""), waste: Math.max(0, n(c.created_count) - n(c.published_count)) }))
    .sort((a, b) => b.waste - a.waste).slice(0, 12);
  const topUsers = [...users]
    .sort((a, b) => n(b.created_mins) - n(a.created_mins)).slice(0, 10)
    .map(u => ({ name: String(u.user_name || ""), compute: pf(n(u.created_mins) / 60) }));
  const scatterData = users
    .map(u => ({ compute: pf(n(u.created_mins) / 60), rate: pf(n(u.publish_rate), 1), name: String(u.user_name || "") }))
    .filter(d => d.compute > 0);

  // ── KPI card arrays — first 2 shown by default, rest shown on expand ───────
  const coreFunnelCards = [
    { title: "Uploaded Clips",     value: n(s.total_uploaded).toLocaleString(),                                           icon: UploadCloud, change: chg("uploaded_count"), changeType: ct("uploaded_count"), insight: `${n(s.total_uploaded).toLocaleString()} source videos ingested. MoM trend reflects content pipeline health.` },
    { title: "AI Generated Clips", value: n(s.total_ai_generated_clips).toLocaleString(),                                 icon: Settings,    change: chg("created_count"),   changeType: ct("created_count"),   insight: `Frammer produced ${n(s.total_ai_generated_clips).toLocaleString()} clips — ${f2(s.ai_content_multiplier)}× per upload.` },
    { title: "Published Clips",    value: n(s.total_published_clips).toLocaleString(),                                    icon: FileCheck,   change: chg("published_count"), changeType: ct("published_count"), insight: `Only ${n(s.total_published_clips)} of ${n(s.total_ai_generated_clips).toLocaleString()} generated clips published (${f2(s.global_publish_rate)}%).` },
    { title: "Publish Rate",       value: `${f2(s.global_publish_rate)}%`,                                                icon: Percent,     insight: `${f2(s.global_publish_rate)}% of AI clips reach a platform. Industry target is typically 5–15%.` },
    { title: "Upload→Publish %",   value: `${f2(s.upload_to_publish_conv_rate)}%`,                                        icon: TrendingUp,  insight: `${f2(s.upload_to_publish_conv_rate)}% of source uploads result in at least one published clip end-to-end.` },
    { title: "Unpublished Gap",    value: n(n(s.total_ai_generated_clips) - n(s.total_published_clips)).toLocaleString(), icon: TrendingDown, insight: `${n(n(s.total_ai_generated_clips) - n(s.total_published_clips)).toLocaleString()} clips created but never published — wasted compute.` },
  ];

  const aiEfficiencyCards = [
    { title: "AI Content Multiplier", value: `${f2(s.ai_content_multiplier)}×`,    icon: Zap,        insight: `Each upload generates ${f2(s.ai_content_multiplier)} AI clips. Higher is better for content production ROI.` },
    { title: "Compute Waste Rate",    value: `${f2(s.ai_compute_waste_rate)}%`,     icon: XCircle,    insight: `${f2(s.ai_compute_waste_rate)}% of AI generation effort never reaches a platform.` },
    { title: "Avg Clips per Publish", value: `${f2(s.avg_compute_cost_per_pub)}×`,  icon: Settings,   insight: `It takes ${f2(s.avg_compute_cost_per_pub)} generated clips to produce one published clip.` },
    { title: "AI Efficiency Score",   value: `${aiScore}/100`,                       icon: Star,       insight: `Score of ${aiScore} = ${aiScore < 30 ? "low" : aiScore < 60 ? "moderate" : "high"} efficiency. Target >50.` },
    { title: "Create→Publish Rate",   value: `${f2(s.global_publish_rate)}%`,        icon: Target,     insight: `${f2(s.global_publish_rate)}% of AI-created clips approved. Editorial filter is very tight.` },
    { title: "Create Multiplier",     value: `${f2(s.ai_content_multiplier)}×`,      icon: TrendingUp, insight: `${f2(s.ai_content_multiplier)} outputs per input. Drives content diversity but raises editorial overhead.` },
  ];

  const durationCards = [
    { title: "Total Compute Hours",   value: `${f1(s.total_server_compute_hrs)} hrs`, icon: Clock,       insight: `${f1(s.total_server_compute_hrs)} hrs of AI processing across all channels.` },
    { title: "Total Published Hours", value: `${f1(s.total_published_hrs)} hrs`,      icon: FileCheck,   insight: `${f1(s.total_published_hrs)} hrs delivered to platforms from ${f1(s.total_server_compute_hrs)} hrs processed.` },
    { title: "YouTube Workload",      value: `${f1(ytHours)} hrs`,                    icon: Radio,       insight: `${f1(ytHours)} hrs published to YouTube — the platform's largest distribution channel.` },
    { title: "Avg Monthly Uploads",   value: f1(s.avg_monthly_uploads),               icon: UploadCloud, insight: `${f1(s.avg_monthly_uploads)} source videos uploaded per month on average.` },
    { title: "Avg Monthly Created",   value: f1(s.avg_monthly_created),               icon: Settings,    insight: `${f1(s.avg_monthly_created)} AI clips generated monthly — ${f2(n(s.avg_monthly_created) / Math.max(n(s.avg_monthly_uploads), 1))}× upload volume.` },
    { title: "Avg Monthly Published", value: f1(s.avg_monthly_published),             icon: FileCheck,   insight: `Only ${f1(s.avg_monthly_published)} clips published per month from ${f1(s.avg_monthly_created)} generated.` },
  ];

  const channelHealthCards = [
    { title: "Best Channel",          value: String(s.best_channel_name || "—"),          icon: Award,        insight: `Channel ${s.best_channel_name} leads with ${f2(s.best_channel_publish_rate)}% publish rate — platform benchmark.` },
    { title: "Best Channel Pub Rate", value: `${f2(s.best_channel_publish_rate)}%`,        icon: Percent,      insight: `Top channel publishes ${f2(s.best_channel_publish_rate)}% vs ${f2(s.global_publish_rate)}% platform average.` },
    { title: "Dead Channels %",       value: `${f2(s.dead_channel_pct)}%`,                icon: TrendingDown, insight: `${f2(s.dead_channel_pct)}% of channels have zero published clips — consuming compute with no value.` },
    { title: "Active Channel Ratio",  value: `${f2(s.active_channel_ratio)}%`,            icon: TrendingUp,   insight: `Only ${f2(s.active_channel_ratio)}% of channels actively publish — large untapped distribution potential.` },
    { title: "Ch A Contribution",     value: `${f2(s.ch_a_contribution_pct)}%`,           icon: BarChart2,    insight: `Channel A accounts for ${f2(s.ch_a_contribution_pct)}% of all publishes${n(s.ch_a_contribution_pct) > 50 ? " — concentration risk" : ""}.` },
    { title: "Zero Value Users",      value: String(n(s.zero_value_users)),                icon: Users,        insight: `${n(s.zero_value_users)} users created content but never had anything published.` },
  ];

  const userHighlightCards = [
    { title: "Top Volume User",      value: String(s.top_volume_user || "—"),          icon: Users,         insight: `${s.top_volume_user} drives significant share of source content volume.` },
    { title: "Best Efficiency User", value: String(s.best_efficiency_user || "—"),     icon: Star,          insight: `${s.best_efficiency_user} achieves ${f2(s.best_efficiency_pub_rate)}% publish rate — study their workflow.` },
    { title: "Best User Pub Rate",   value: `${f2(s.best_efficiency_pub_rate)}%`,      icon: Percent,       insight: `${f2(s.best_efficiency_pub_rate)}% is the top individual rate — ${f2(n(s.best_efficiency_pub_rate) / Math.max(n(s.global_publish_rate), 0.01))}× the platform average.` },
    { title: "Zero Value Users",     value: String(n(s.zero_value_users)),             icon: AlertTriangle, insight: `${n(s.zero_value_users)} users add compute load but publish nothing — investigate blockers.` },
    { title: "Avg Monthly Uploads",  value: f1(s.avg_monthly_uploads),                 icon: UploadCloud,   insight: `${f1(s.avg_monthly_uploads)} avg monthly uploads. Top users likely far exceed this.` },
    { title: "Avg Monthly Published",value: f1(s.avg_monthly_published),               icon: FileCheck,     insight: `${f1(s.avg_monthly_published)} avg monthly publishes — reflecting high editorial standards.` },
  ];

  const languageCards = [
    { title: "English Publish Rate", value: `${f2(s.en_publish_rate)}%`,             icon: Globe,         insight: `English content achieves ${f2(s.en_publish_rate)}% — highest language publish rate.` },
    { title: "Hindi Publish Rate",   value: `${f2(s.hi_publish_rate)}%`,             icon: Globe,         insight: `Hindi publish rate ${f2(s.hi_publish_rate)}% — ${f2(n(s.en_publish_rate) / Math.max(n(s.hi_publish_rate), 0.01))}× lower than English.` },
    { title: "EN/HI Efficacy ×",    value: `${f2(s.en_hi_efficacy_multiplier)}×`,   icon: TrendingUp,    insight: `English is ${f2(s.en_hi_efficacy_multiplier)}× more likely to be published than Hindi.` },
    { title: "EN Generation Cost",  value: `${f1(s.en_gen_cost)}× per publish`,     icon: Settings,      insight: `${f1(s.en_gen_cost)} English clips generated per published clip.` },
    { title: "HI Generation Cost",  value: `${f1(s.hi_gen_cost)}× per publish`,     icon: Settings,      insight: `${f1(s.hi_gen_cost)} Hindi clips per publish — ${f2(n(s.hi_gen_cost) / Math.max(n(s.en_gen_cost), 1))}× less efficient than English.` },
    { title: "Unknown Team %",      value: `${f2(s.unknown_team_attribution_pct)}%`, icon: AlertTriangle, insight: `${f2(s.unknown_team_attribution_pct)}% of videos have no team data — team analysis impossible.` },
  ];

  const monthlyBenchmarkCards = [
    { title: "Peak Workload Month", value: String(s.peak_workload_month || "—"),         icon: Calendar,   insight: `${s.peak_workload_month} was the busiest AI generation month — possible campaign spike.` },
    { title: "Peak Workload Clips", value: n(s.peak_workload_clips).toLocaleString(),    icon: Settings,   insight: `${n(s.peak_workload_clips).toLocaleString()} clips in one month — ${f2(n(s.peak_workload_clips) / Math.max(n(s.avg_monthly_created), 1))}× the monthly average.` },
    { title: "Peak Slice Ratio",    value: `${f2(s.peak_slice_ratio)}×`,                 icon: Zap,        insight: `At peak, each upload generated ${f2(s.peak_slice_ratio)} clips vs ${f2(s.ai_content_multiplier)}× overall average.` },
    { title: "Peak Value Month",    value: String(s.peak_value_month || "—"),            icon: Star,       insight: `${s.peak_value_month} had the most published clips — ${n(s.peak_value_pub_count)} delivered.` },
    { title: "Peak Published Clips",value: n(s.peak_value_pub_count).toLocaleString(),   icon: FileCheck,  insight: `${n(s.peak_value_pub_count)} published in the best month — ${f2(n(s.peak_value_pub_count) / Math.max(n(s.avg_monthly_published), 1))}× the monthly average.` },
    { title: "Dec→Feb Upload Surge",value: `${f1(s.dec_to_feb_upload_surge_pct)}%`,      icon: TrendingUp, insight: `Upload volume ${n(s.dec_to_feb_upload_surge_pct) > 0 ? "grew" : "fell"} ${f1(Math.abs(n(s.dec_to_feb_upload_surge_pct)))}% from Dec 2025 to Feb 2026.` },
  ];

  // ── One-line heading insights (shown inline beside label, hidden when expanded) ──
  const hi = {
    coreFunnel:       `${f2(s.global_publish_rate)}% publish rate — ${n(n(s.total_ai_generated_clips) - n(s.total_published_clips)).toLocaleString()} clips wasted`,
    aiEfficiency:     `${f2(s.ai_compute_waste_rate)}% waste — ${aiScore}/100 efficiency score`,
    duration:         `${f1(s.total_server_compute_hrs)} hrs processed, ${f1(s.total_published_hrs)} hrs published`,
    channelHealth:    `${f2(s.dead_channel_pct)}% dead channels — Ch ${s.best_channel_name} leads at ${f2(s.best_channel_publish_rate)}%`,
    userHighlights:   `${s.top_volume_user || "—"} top uploader — ${n(s.zero_value_users)} zero-publish users`,
    language:         `English ${f2(s.en_hi_efficacy_multiplier)}× more effective than Hindi`,
    monthlyBenchmarks:`Peak ${s.peak_workload_month || "—"}: ${n(s.peak_workload_clips).toLocaleString()} clips · ${f1(s.dec_to_feb_upload_surge_pct)}% Dec→Feb surge`,
  };

  return (
    <DashboardLayout title="Executive Overview">

      <KpiSection icon={BarChart2} label="Core Funnel"           color="text-indigo-400" cards={coreFunnelCards}       previewCount={3} headingInsight={hi.coreFunnel} />
      <KpiSection icon={Zap}       label="AI Efficiency"         color="text-yellow-400" cards={aiEfficiencyCards}     previewCount={3} headingInsight={hi.aiEfficiency} />
      <KpiSection icon={Clock}     label="Duration & Compute"    color="text-cyan-400"   cards={durationCards}         previewCount={3} headingInsight={hi.duration} />
      <KpiSection icon={Radio}     label="Channel Health"        color="text-green-400"  cards={channelHealthCards}    previewCount={3} headingInsight={hi.channelHealth} />
      <KpiSection icon={Users}     label="User Highlights"       color="text-purple-400" cards={userHighlightCards}    previewCount={3} headingInsight={hi.userHighlights} />
      <KpiSection icon={Globe}     label="Language Intelligence" color="text-teal-400"   cards={languageCards}         previewCount={3} headingInsight={hi.language} />
      <KpiSection icon={Calendar}  label="Monthly Benchmarks"    color="text-orange-400" cards={monthlyBenchmarkCards} previewCount={3} headingInsight={hi.monthlyBenchmarks} />

      {/* ── FUNNEL & WASTE ────────────────────────────────────────── */}
      <SectionLabel icon={Target} label="Funnel & Waste" color="text-red-400" />
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        <ChartCard title="AI Pipeline Funnel"
          insight="Volume drops sharply from Generated → Published. The bottleneck is editorial review, not AI generation capacity.">
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={funnelBars} layout="vertical">
              <XAxis type="number" {...AX} />
              <YAxis type="category" dataKey="stage" {...AX} width={75} />
              <Tooltip {...TT} />
              <Bar dataKey="value" fill={C.indigo} radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Published vs Wasted Clips"
          insight="The vast majority of AI-generated clips are never published — representing wasted compute cost that could be reduced by tuning generation volume.">
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={[
              { name: "Published", value: n(s.total_published_clips) },
              { name: "Wasted",    value: Math.max(0, n(s.total_ai_generated_clips) - n(s.total_published_clips)) },
            ]}>
              <XAxis dataKey="name" {...AX} /><YAxis {...AX} />
              <Tooltip {...TT} />
              <Bar dataKey="value" fill={C.orange} radius={4} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <div className="rounded-xl border bg-card p-5">
          <h3 className="mb-4 text-sm font-semibold">Funnel Drop-off</h3>
          <div className="space-y-3">
            {[
              { label: "Upload → Generate", pct: funnel?.rates?.upload_to_create_pct,  color: C.blue,   icon: "📤" },
              { label: "Generate → Publish",pct: funnel?.rates?.create_to_publish_pct, color: C.green,  icon: "🚀" },
              { label: "Upload → Publish",  pct: funnel?.rates?.upload_to_publish_pct, color: C.indigo, icon: "✅" },
              { label: "Drop-off Rate",     pct: funnel?.rates?.drop_off_pct,          color: C.red,    icon: "⚠️" },
            ].map(({ label, pct, color, icon }) => (
              <div key={label} className="flex items-center justify-between">
                <span className="text-xs text-muted-foreground">{icon} {label}</span>
                <div className="flex items-center gap-2">
                  <div className="w-20 h-1.5 rounded-full bg-muted overflow-hidden">
                    <div className="h-full rounded-full" style={{ width: `${Math.min(n(pct), 100)}%`, background: color }} />
                  </div>
                  <span className="text-xs font-semibold w-12 text-right" style={{ color }}>{pf(n(pct), 1)}%</span>
                </div>
              </div>
            ))}
            <div className="mt-4 pt-3 border-t border-border space-y-2">
              <StatRow label="Compute waste rate" value={`${f2(s.ai_compute_waste_rate)}%`} />
              <StatRow label="Clips per publish"  value={`${f1(s.avg_compute_cost_per_pub)} clips`} />
              <StatRow label="AI multiplier"      value={`${f2(s.ai_content_multiplier)}×`} />
            </div>
          </div>
        </div>
      </div>

      {/* ── TREND CHARTS ─────────────────────────────────────────── */}
      <SectionLabel icon={TrendingUp} label="Trend Charts" color="text-blue-400" />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">

        <ChartCard title="Pipeline Trend (Uploaded / Generated / Published)"
          insight="Upload and generation volumes surge from Dec 2025 into Feb 2026, while published volume stays flat — the compute waste gap is widening every month.">
          {pipelineData.length === 0 ? <NoData /> :
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={pipelineData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a2a2a" />
                <XAxis dataKey="month" {...AX} /><YAxis {...AX} />
                <Tooltip {...TT} /><Legend wrapperStyle={{ fontSize: 11 }} />
                <Line type="monotone" dataKey="uploaded"  stroke={C.blue}   strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="generated" stroke={C.green}  strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="published" stroke={C.indigo} strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>}
        </ChartCard>

        <ChartCard title="Duration Trend (hours)"
          insight="Generated duration grows much faster than published duration — a growing backlog of content is being created but not reaching audiences.">
          {durationData.length === 0 ? <NoData /> :
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={durationData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a2a2a" />
                <XAxis dataKey="month" {...AX} /><YAxis {...AX} />
                <Tooltip {...TT} /><Legend wrapperStyle={{ fontSize: 11 }} />
                <Line type="monotone" dataKey="uploaded"  stroke={C.blue}   strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="generated" stroke={C.green}  strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="published" stroke={C.indigo} strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>}
        </ChartCard>

        <ChartCard title="Publish Rate Trend (%)"
          insight="Publish rate fluctuates month to month. Peaks indicate active editorial periods. A sustained decline is a pipeline health warning sign.">
          {publishRateData.length === 0 ? <NoData /> :
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={publishRateData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a2a2a" />
                <XAxis dataKey="month" {...AX} /><YAxis unit="%" {...AX} />
                <Tooltip {...TT} />
                <Line type="monotone" dataKey="rate" stroke={C.indigo} strokeWidth={2} dot={{ r: 3, fill: C.indigo }} />
              </LineChart>
            </ResponsiveContainer>}
        </ChartCard>

        <ChartCard title="User Efficiency (Compute hrs vs Publish %)"
          insight="Ideal users sit in the top-right: high compute hours AND high publish rate. High compute + low publish rate users are the biggest efficiency optimisation targets.">
          {scatterData.length === 0 ? <NoData /> :
            <ResponsiveContainer width="100%" height={260}>
              <ScatterChart>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a2a2a" />
                <XAxis type="number" dataKey="compute" name="Compute hrs" {...AX} />
                <YAxis type="number" dataKey="rate"    name="Publish %"  {...AX} />
                <Tooltip {...TT} cursor={{ strokeDasharray: "3 3" }} />
                <Scatter data={scatterData} fill={C.purple} />
              </ScatterChart>
            </ResponsiveContainer>}
        </ChartCard>

        <ChartCard title="Compute Waste by Channel"
          insight="Channels with tall bars generate many clips that never get published. Prioritise improving editorial throughput or reduce generation volume for these channels.">
          {channelWaste.length === 0 ? <NoData /> :
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={channelWaste}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a2a2a" />
                <XAxis dataKey="name" {...AX} /><YAxis {...AX} />
                <Tooltip {...TT} />
                <Bar dataKey="waste" fill={C.red} radius={[4, 4, 0, 0]} name="Unpublished gap" />
              </BarChart>
            </ResponsiveContainer>}
        </ChartCard>

        <ChartCard title="Top 10 Users by Compute Hours"
          insight="These users drive the most AI generation load. Cross-reference with publish rates — high compute with low publish rate signals wasted effort that can be addressed.">
          {topUsers.length === 0 ? <NoData /> :
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={topUsers} layout="vertical">
                <XAxis type="number" {...AX} />
                <YAxis type="category" dataKey="name" {...AX} width={85} />
                <Tooltip {...TT} />
                <Bar dataKey="compute" fill={C.green} radius={[0, 4, 4, 0]} name="Compute hrs" />
              </BarChart>
            </ResponsiveContainer>}
        </ChartCard>

      </div>

      <InsightsSection s={s} />

    </DashboardLayout>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// SHARED SUB-COMPONENTS
// ─────────────────────────────────────────────────────────────────────────────
// ─── AI Insights section — shown at bottom of page ──────────────────────────
function InsightsSection({ s }) {
  const n2 = (v) => Number(v ?? 0);

  const insights = useMemo(() => {
    const list = [];

    const pr = n2(s.global_publish_rate);
    if (pr > 0)
      list.push({
        severity: pr < 2 ? "high" : pr < 5 ? "medium" : "info",
        title: `Global publish rate is ${pr.toFixed(2)}%`,
        detail: `${(100 - pr).toFixed(1)}% of AI-generated clips are never published. ${(n2(s.total_ai_generated_clips) - n2(s.total_published_clips)).toLocaleString()} clips represent unused compute.`,
      });

    const mult = n2(s.ai_content_multiplier);
    if (mult > 0)
      list.push({
        severity: "info",
        title: `AI multiplier: ${mult.toFixed(2)}× — each upload generates ${mult.toFixed(1)} clips`,
        detail: `Frammer creates ${mult.toFixed(1)} output clips per uploaded source video. This is the core product value metric.`,
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
        detail: `Hindi content is heavily processed but rarely published. Workflow or editorial prioritisation gap needs investigation.`,
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
            className={`p-4 rounded-xl border-l-2 text-xs ${
              ins.severity === "high"
                ? "border-red-500 bg-red-500/5 text-red-400"
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


function SectionLabel({ icon: Icon, label, color }) {
  return (
    <div className={`flex items-center gap-2 mb-3 mt-2 ${color}`}>
      <Icon className="h-4 w-4" />
      <span className="text-xs font-bold uppercase tracking-widest">{label}</span>
      <div className="flex-1 h-px bg-border/60 ml-1" />
    </div>
  );
}

function ChartCard({ title, insight, children }) {
  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }}
      className="rounded-xl border bg-card p-5">
      <h3 className="mb-3 text-sm font-semibold text-foreground">{title}</h3>
      {children}
      {insight && (
        <div className="mt-3 pt-3 border-t border-border/40 flex gap-2 text-[11px] text-muted-foreground leading-relaxed">
          <Lightbulb className="h-3.5 w-3.5 shrink-0 mt-0.5 text-yellow-400" />
          <span>{insight}</span>
        </div>
      )}
    </motion.div>
  );
}

function NoData() {
  return <div className="flex h-[260px] items-center justify-center text-sm text-muted-foreground">No data — run ETL pipeline first</div>;
}

function StatRow({ label, value }) {
  return (
    <div className="flex justify-between text-xs">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-semibold text-foreground">{value}</span>
    </div>
  );
}