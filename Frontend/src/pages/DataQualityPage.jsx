/**
 * src/pages/DataQualityPage.jsx
 *
 * Uses ONLY GET /api/data-quality/checks
 * Shows all validation results organised as:
 *   1. Summary KPIs (score, pass/warn/fail counts, last run)
 *   2. Quality score bar chart per file/table
 *   3. Per-file expandable cards with full check table
 *   4. All-checks search + filter panel
 */

import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { motion, AnimatePresence } from "framer-motion";
import {
  CheckCircle, XCircle, AlertTriangle, RefreshCw,
  Shield, FileText, Database, ChevronDown, ChevronUp, Search,
} from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";

const API = "http://localhost:8000";
const TT = { contentStyle: { background: "#1a1b1e", border: "1px solid #333", borderRadius: 8, fontSize: 11, color: "#e0e0e0" } };
const AX = { tick: { fontSize: 10, fill: "#888" }, axisLine: false, tickLine: false };

// ─── Helpers ──────────────────────────────────────────────────────────────────

function friendlyFile(raw) {
  if (!raw) return "—";
  return raw
    .replace("CLIENT1-channels.csv", "channels.csv")
    .replace("channel-wise-publishing-duration.csv", "pub-duration.csv")
    .replace("channel-wise-publishing.csv", "publishing.csv")
    .replace("channel_user.csv", "channel×user.csv");
}

function fileScore(fail, warn) {
  return Math.max(0, 100 - fail * 15 - warn * 8);
}

async function fetchChecks() {
  try {
    const r = await fetch(`${API}/api/data-quality/checks`);
    if (!r.ok) throw new Error(r.status);
    return r.json();
  } catch (e) {
    console.error("[DQ]", e.message);
    return null;
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// PAGE
// ─────────────────────────────────────────────────────────────────────────────

export default function DataQualityPage() {

  const [expanded, setExpanded] = useState(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");

  const { data: raw, isLoading, refetch } = useQuery({
    queryKey: ["dqChecks"],
    queryFn: fetchChecks,
    staleTime: 30000,
  });

  // ── Derived ─────────────────────────────────────────────────────────────────
  const total = raw?.total || 0;
  const nFail = raw?.fail || 0;
  const nWarn = raw?.warn || 0;
  const nPass = raw?.pass || 0;
  const ranAt = raw?.ran_at;
  const byFile = raw?.by_file || {};
  const allChecks = raw?.checks || [];

  // Sort files: FAIL first → WARN → PASS
  const sortedFiles = useMemo(() =>
    Object.entries(byFile).sort(([, a], [, b]) => {
      if (b.fail !== a.fail) return b.fail - a.fail;
      return b.warn - a.warn;
    }),
    [byFile]
  );

  // Bar chart: one bar per file
  const chartData = useMemo(() =>
    sortedFiles
      .filter(([, d]) => d.fail + d.warn + d.pass > 0)
      .map(([file, d]) => ({
        name: friendlyFile(file).replace(".csv", "").slice(0, 22),
        score: fileScore(d.fail, d.warn),
        fail: d.fail,
        warn: d.warn,
      })),
    [sortedFiles]
  );

  const overallScore = chartData.length
    ? Math.round(chartData.reduce((s, d) => s + d.score, 0) / chartData.length)
    : 0;

  // Filtered all-checks list
  const filteredChecks = useMemo(() => {
    let list = allChecks;
    if (statusFilter !== "ALL") list = list.filter(c => c.status === statusFilter);
    const q = search.trim().toLowerCase();
    if (q) list = list.filter(c =>
      c.name.toLowerCase().includes(q) ||
      c.message.toLowerCase().includes(q) ||
      (c.table || "").toLowerCase().includes(q)
    );
    return list;
  }, [allChecks, statusFilter, search]);

  // ── Loading ──────────────────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <DashboardLayout title="Data Quality">
        <div className="flex items-center justify-center h-64 gap-2 text-muted-foreground text-sm">
          <RefreshCw className="h-4 w-4 animate-spin" /> Loading validation results…
        </div>
      </DashboardLayout>
    );
  }

  // ── Empty ────────────────────────────────────────────────────────────────────
  if (!raw || total === 0) {
    return (
      <DashboardLayout title="Data Quality">
        <div className="rounded-xl border border-border bg-card p-14 text-center">
          <Shield className="h-12 w-12 mx-auto mb-4 text-muted-foreground/20" />
          <p className="text-sm text-muted-foreground mb-1">No validation results yet.</p>
          <p className="text-xs text-muted-foreground">
            Save a CSV in <code className="font-mono bg-muted px-1 rounded">data/raw/</code> or
            call <code className="font-mono bg-muted px-1 rounded">POST /api/etl/run</code>
          </p>
        </div>
      </DashboardLayout>
    );
  }

  // ── Render ────────────────────────────────────────────────────────────────────
  return (
    <DashboardLayout title="Data Quality">

      {/* ── Summary KPIs ──────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-6">
        <KpiTile
          label="Quality Score"
          value={`${overallScore}/100`}
          icon={Shield}
          color={overallScore >= 80 ? "text-green-400" : overallScore >= 50 ? "text-yellow-400" : "text-red-400"}
        />
        <KpiTile label="Total Checks" value={total} icon={FileText} color="text-blue-400" />
        <KpiTile label="Passed" value={nPass} icon={CheckCircle} color="text-green-400" />
        <KpiTile label="Warnings" value={nWarn} icon={AlertTriangle} color="text-yellow-400" />
        <KpiTile label="Failed" value={nFail} icon={XCircle} color="text-red-400" />
        <KpiTile
          label="Last Validated"
          value={ranAt ? new Date(ranAt).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "Never"}
          icon={RefreshCw}
          color="text-muted-foreground"
        />
      </div>

      {/* ── Score chart ───────────────────────────────────────────────────── */}
      <div className="mb-6 rounded-xl border bg-card p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold">Quality Score by File / Table</h3>
          <button
            onClick={() => refetch()}
            className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            <RefreshCw className="h-3.5 w-3.5" /> Refresh
          </button>
        </div>

        <ResponsiveContainer width="100%" height={Math.max(180, chartData.length * 22)}>
          <BarChart data={chartData} layout="vertical">
            <XAxis type="number" domain={[0, 100]} unit="%" {...AX} />
            <YAxis dataKey="name" type="category" {...AX} width={165} />
            <Tooltip {...TT} formatter={v => [`${v}/100`, "Score"]} />
            <Bar dataKey="score" radius={[0, 4, 4, 0]}>
              {chartData.map((d, i) => (
                <Cell key={i}
                  fill={d.fail > 0 ? "#ef4444" : d.warn > 0 ? "#f59e0b" : "#22c55e"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>

        <div className="mt-3 pt-3 border-t border-border/40 flex gap-2 text-[11px] text-muted-foreground mb-2">
          <span className="text-yellow-400 shrink-0">💡</span>
          <span>Files scoring below 80 have significant issues. Each failed check costs 15 points; each warning costs 8. Fix the lowest-scoring files first — they pose the greatest risk to analytics accuracy.</span>
        </div>
        <div className="flex items-center gap-5 mt-3 text-xs text-muted-foreground">
          <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm bg-red-400 inline-block" />Has failures</span>
          <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm bg-yellow-400 inline-block" />Has warnings</span>
          <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm bg-green-400 inline-block" />All passing</span>
        </div>
      </div>

      {/* ── Per-file cards ────────────────────────────────────────────────── */}
      <h3 className="text-sm font-semibold mb-3">
        Validation Results by File
        <span className="ml-2 text-xs font-normal text-muted-foreground">
          — click any row to expand checks
        </span>
      </h3>

      <div className="space-y-2 mb-8">
        {sortedFiles.map(([file, data], idx) => {
          const score = fileScore(data.fail, data.warn);
          const isDb = file.startsWith("db:");
          const isOpen = expanded === idx;
          const border = data.fail > 0 ? "border-red-500/40"
            : data.warn > 0 ? "border-yellow-500/30"
              : "border-green-500/25";

          return (
            <div key={file} className={`rounded-xl border ${border} bg-card overflow-hidden`}>
              <button
                onClick={() => setExpanded(isOpen ? null : idx)}
                className="w-full flex items-center gap-3 px-5 py-3.5 text-left hover:bg-muted/20 transition-colors"
              >
                {/* Icon */}
                {isDb
                  ? <Database className={`h-4 w-4 shrink-0 ${data.fail > 0 ? "text-red-400" : data.warn > 0 ? "text-yellow-400" : "text-blue-400"}`} />
                  : data.fail > 0 ? <XCircle className="h-4 w-4 shrink-0 text-red-400" />
                    : data.warn > 0 ? <AlertTriangle className="h-4 w-4 shrink-0 text-yellow-400" />
                      : <CheckCircle className="h-4 w-4 shrink-0 text-green-400" />}

                {/* Name */}
                <span className="flex-1 text-sm font-medium font-mono truncate">
                  {friendlyFile(file)}
                </span>

                {/* Badges */}
                <div className="flex items-center gap-2.5 text-xs shrink-0">
                  {data.fail > 0 && <Pill color="bg-red-500/10    text-red-400" label={`${data.fail} FAIL`} />}
                  {data.warn > 0 && <Pill color="bg-yellow-500/10 text-yellow-500" label={`${data.warn} WARN`} />}
                  {data.pass > 0 && <Pill color="bg-green-500/10  text-green-400" label={`${data.pass} PASS`} />}

                  <span className={`px-2 py-0.5 rounded-full text-[11px] font-bold ${score >= 80 ? "bg-green-500/10 text-green-400" :
                      score >= 50 ? "bg-yellow-500/10 text-yellow-500" :
                        "bg-red-500/10 text-red-400"
                    }`}>{score}/100</span>

                  {isOpen
                    ? <ChevronUp className="h-4 w-4 text-muted-foreground" />
                    : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
                </div>
              </button>

              <AnimatePresence>
                {isOpen && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.16 }}
                    className="overflow-hidden"
                  >
                    <div className="border-t border-border/40 overflow-x-auto">
                      <table className="min-w-full text-xs">
                        <thead className="bg-muted/30">
                          <tr>
                            {["Status", "Check", "Message", "Count", "%"].map(h => (
                              <th key={h} className="px-3 py-2 text-left font-semibold text-muted-foreground whitespace-nowrap">{h}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {data.checks.map((c, ci) => (
                            <tr key={ci} className="border-t border-border/30 hover:bg-muted/10">
                              <td className="px-3 py-2"><StatusPill status={c.status} /></td>
                              <td className="px-3 py-2 font-mono text-[10px] text-muted-foreground max-w-[210px] truncate" title={c.name}>{c.name}</td>
                              <td className="px-3 py-2 max-w-sm leading-snug">{c.message}</td>
                              <td className="px-3 py-2 text-right whitespace-nowrap">
                                {c.count > 0
                                  ? <span className="font-mono">{c.count.toLocaleString()}</span>
                                  : <span className="text-muted-foreground/40">—</span>}
                              </td>
                              <td className="px-3 py-2 text-right whitespace-nowrap">
                                {c.pct > 0
                                  ? <span className={c.pct > 80 ? "text-red-400 font-bold" : c.pct > 20 ? "text-yellow-500" : "text-muted-foreground"}>
                                    {c.pct}%
                                  </span>
                                  : <span className="text-muted-foreground/40">—</span>}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          );
        })}
      </div>

      {/* ── All checks: search + filter ───────────────────────────────────── */}
      <div className="rounded-xl border bg-card p-5">
        <h3 className="text-sm font-semibold mb-4">
          Search All {total} Checks
        </h3>

        <div className="flex flex-col sm:flex-row gap-3 mb-4">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search by check name, message or file…"
              className="w-full pl-9 pr-3 h-9 rounded-lg border border-border bg-muted/20 text-sm placeholder:text-muted-foreground/50 outline-none focus:border-primary transition-colors"
            />
          </div>
          <div className="flex gap-1.5 flex-wrap">
            {[
              { key: "ALL", label: `All (${total})` },
              { key: "FAIL", label: `FAIL (${nFail})` },
              { key: "WARN", label: `WARN (${nWarn})` },
              { key: "PASS", label: `PASS (${nPass})` },
            ].map(({ key, label }) => (
              <button key={key} onClick={() => setStatusFilter(key)}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition-colors ${statusFilter === key
                    ? key === "FAIL" ? "bg-red-500/20 text-red-400 border-red-500/40"
                      : key === "WARN" ? "bg-yellow-500/20 text-yellow-500 border-yellow-500/40"
                        : key === "PASS" ? "bg-green-500/20 text-green-400 border-green-500/40"
                          : "bg-primary/20 text-primary border-primary/40"
                    : "bg-muted/30 text-muted-foreground border-border/50 hover:bg-muted/60"
                  }`}>
                {label}
              </button>
            ))}
          </div>
        </div>

        <div className="overflow-auto rounded-lg border border-border">
          <table className="min-w-full text-xs">
            <thead className="bg-muted/40 sticky top-0">
              <tr>
                {["Status", "File / Table", "Check Name", "Message", "Count", "%"].map(h => (
                  <th key={h} className="px-3 py-2 text-left font-semibold text-muted-foreground whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filteredChecks.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-3 py-10 text-center text-muted-foreground">
                    No checks match your filter.
                  </td>
                </tr>
              ) : filteredChecks.map((c, i) => (
                <tr key={i} className="border-t border-border/30 hover:bg-muted/10">
                  <td className="px-3 py-2"><StatusPill status={c.status} /></td>
                  <td className="px-3 py-2 font-mono text-[10px] text-muted-foreground whitespace-nowrap">
                    {friendlyFile(c.table || "—")}
                  </td>
                  <td className="px-3 py-2 font-mono text-[10px] text-muted-foreground max-w-[180px] truncate" title={c.name}>
                    {c.name}
                  </td>
                  <td className="px-3 py-2 max-w-xs leading-snug">{c.message}</td>
                  <td className="px-3 py-2 text-right whitespace-nowrap">
                    {c.count > 0
                      ? <span className="font-mono">{c.count.toLocaleString()}</span>
                      : <span className="text-muted-foreground/40">—</span>}
                  </td>
                  <td className="px-3 py-2 text-right whitespace-nowrap">
                    {c.pct > 0
                      ? <span className={c.pct > 80 ? "text-red-400 font-bold" : c.pct > 20 ? "text-yellow-500" : "text-muted-foreground"}>
                        {c.pct}%
                      </span>
                      : <span className="text-muted-foreground/40">—</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <p className="mt-2 text-xs text-muted-foreground">
          Showing {filteredChecks.length.toLocaleString()} of {total.toLocaleString()} checks
          {ranAt && ` · Last run ${new Date(ranAt).toLocaleString()}`}
        </p>
      </div>

    </DashboardLayout>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Micro-components
// ─────────────────────────────────────────────────────────────────────────────

function KpiTile({ label, value, icon: Icon, color }) {
  return (
    <div className="rounded-xl border bg-card p-4 flex items-start gap-3">
      <div className={`mt-0.5 ${color}`}><Icon className="h-4 w-4" /></div>
      <div className="min-w-0">
        <p className="text-[11px] text-muted-foreground uppercase tracking-wider truncate">{label}</p>
        <p className="text-xl font-bold mt-0.5 truncate">{value}</p>
      </div>
    </div>
  );
}

function StatusPill({ status }) {
  const s = {
    FAIL: "bg-red-500/15    text-red-400    border border-red-500/30",
    WARN: "bg-yellow-500/15 text-yellow-500  border border-yellow-500/30",
    PASS: "bg-green-500/15  text-green-400   border border-green-500/30",
  };
  return (
    <span className={`inline-flex items-center rounded-full px-1.5 py-0.5 text-[10px] font-bold ${s[status] || s.PASS}`}>
      {status}
    </span>
  );
}

function Pill({ color, label }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold ${color}`}>
      {label}
    </span>
  );
}