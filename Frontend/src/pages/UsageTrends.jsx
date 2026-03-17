import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, BarChart, Bar
} from "recharts";
import { ArrowUp, ArrowDown, GitCompare } from "lucide-react";
import { Button } from "@/components/ui/button";
import { motion } from "framer-motion";

const API = "http://localhost:8000";
const TT = { contentStyle: { background: "#1a1b1e", border: "1px solid #333", borderRadius: 8, fontSize: 11, color: "#e0e0e0" } };
const AX = { tick: { fontSize: 10, fill: "#888" }, axisLine: { stroke: "#333" }, tickLine: false };
const C = { blue: "#06b6d4", green: "#22c55e", red: "#ef4444", orange: "#f59e0b", purple: "#8b5cf6", indigo: "#6366f1" };

async function fetchArr(url) {
  try {
    const r = await fetch(API + url);
    if (!r.ok) return [];
    const d = await r.json();
    return Array.isArray(d) ? d : (Array.isArray(d?.data) ? d.data : []);
  } catch { return []; }
}

// ── Safe number helper ────────────────────────────────────────────
const n = (v) => Number(v || 0);
const f = (v, dp = 1) => parseFloat((n(v)).toFixed(dp));

export default function UsageTrends() {

  const [showComp, setShowComp] = useState(false);

  const { data: monthly = [] } = useQuery({ queryKey: ["monthly"], queryFn: () => fetchArr("/api/monthly"), staleTime: 60000 });
  const { data: outputTypes = [] } = useQuery({ queryKey: ["outputTypes"], queryFn: () => fetchArr("/api/output-types"), staleTime: 60000 });
  const { data: inputTypes = [] } = useQuery({ queryKey: ["inputTypes"], queryFn: () => fetchArr("/api/input-types"), staleTime: 60000 });
  const { data: languages = [] } = useQuery({ queryKey: ["languages"], queryFn: () => fetchArr("/api/languages"), staleTime: 60000 });

  const fmt = (m) => String(m || "").replace(", ", " ");

  // ── Growth ────────────────────────────────────────────────────────
  const growth = (key) => {
    if (monthly.length < 2) return null;
    const c = n(monthly[monthly.length - 1]?.[key]);
    const p = n(monthly[monthly.length - 2]?.[key]);
    return p ? f((c - p) / p * 100) : null;
  };

  // ── Line datasets — all values are parseFloat, never strings ─────
  const makeSet = (key, toHours = false) => monthly.map((m, i) => {
    const cur = toHours ? f(n(m[key]) / 60) : n(m[key]);
    const prev = showComp && monthly[i - 1]
      ? (toHours ? f(n(monthly[i - 1][key]) / 60) : n(monthly[i - 1][key]))
      : undefined;
    return { month: fmt(m.month), current: cur, ...(prev !== undefined ? { previous: prev } : {}) };
  });

  const uploadSet = useMemo(() => makeSet("uploaded_count"), [monthly, showComp]);
  const processSet = useMemo(() => makeSet("created_count"), [monthly, showComp]);
  const publishSet = useMemo(() => makeSet("published_count"), [monthly, showComp]);
  const hoursSet = useMemo(() => makeSet("created_mins", true), [monthly, showComp]);

  // ── Conversion rates ──────────────────────────────────────────────
  const convData = monthly.map(m => ({
    month: fmt(m.month),
    "Upload→Create": f(n(m.uploaded_count) ? n(m.created_count) / n(m.uploaded_count) * 100 : 0),
    "Create→Publish": f(n(m.created_count) ? n(m.published_count) / n(m.created_count) * 100 : 0),
  }));

  // ── Compute efficiency ────────────────────────────────────────────
  const effData = monthly.map(m => ({
    month: fmt(m.month),
    efficiency: f(n(m.created_mins) ? n(m.published_mins) / n(m.created_mins) * 100 : 0),
  }));

  // ── Anomaly detection (2σ) ────────────────────────────────────────
  const anomalies = useMemo(() => {
    if (monthly.length < 4) return [];
    const vals = monthly.map(m => n(m.created_count));
    const mean = vals.reduce((a, b) => a + b, 0) / vals.length;
    const std = Math.sqrt(vals.reduce((s, v) => s + (v - mean) ** 2, 0) / vals.length);
    return monthly.filter(m => Math.abs(n(m.created_count) - mean) > 2 * std);
  }, [monthly]);

  // ── Output / input / language stats ──────────────────────────────
  const outputVol = [...outputTypes]
    .sort((a, b) => n(b.created_count) - n(a.created_count))
    .map(o => ({ type: String(o.output_type || ""), count: n(o.created_count) }));

  const inputVol = [...inputTypes]
    .sort((a, b) => n(b.created_count) - n(a.created_count))
    .slice(0, 8)
    .map(t => ({ type: String(t.input_type || ""), created: n(t.created_count), published: n(t.published_count) }));

  const langData = languages.map(l => ({
    language: String(l.language || ""),
    created: n(l.created_count),
    published: n(l.published_count),
  }));

  const peakMonth = monthly.reduce((mx, m) =>
    n(m.created_count) > n(mx.created_count) ? m : mx, monthly[0] || {});

  return (
    <DashboardLayout title="Usage & Trends">

      {peakMonth?.month && (
        <p className="mb-3 text-xs text-muted-foreground">
          Peak workload: <span className="font-medium text-foreground">
            {peakMonth.month} — {n(peakMonth.created_count).toLocaleString()} clips
          </span>
        </p>
      )}

      <div className="mb-4 flex justify-end">
        <Button variant={showComp ? "default" : "outline"} size="sm" className="gap-2"
          onClick={() => setShowComp(v => !v)}>
          <GitCompare className="h-4 w-4" />
          {showComp ? "Hide" : "Show"} Period Comparison
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">

        {/* Individual trend cards */}
        {[
          { title: "Uploads", data: uploadSet, key: "uploaded_count", color: C.blue },
          { title: "Processed Videos", data: processSet, key: "created_count", color: C.green },
          { title: "Published Videos", data: publishSet, key: "published_count", color: C.indigo },
          { title: "Processing Hours", data: hoursSet, key: "created_mins", color: C.orange },
        ].map(({ title, data, key, color }) => (
          <TrendCard key={title} title={title} data={data} color={color} growth={growth(key)} showComp={showComp} />
        ))}

        {/* Pipeline conversion */}
        <ChartCard title="Pipeline Conversion Rates (%)">
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={convData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2a2a2a" />
              <XAxis dataKey="month" {...AX} />
              <YAxis unit="%" {...AX} />
              <Tooltip {...TT} /><Legend wrapperStyle={{ fontSize: 10 }} />
              <Line dataKey="Upload→Create" stroke={C.green} strokeWidth={2} dot={false} />
              <Line dataKey="Create→Publish" stroke={C.indigo} strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        {/* Compute efficiency */}
        <ChartCard title="Compute Efficiency %">
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={effData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2a2a2a" />
              <XAxis dataKey="month" {...AX} />
              <YAxis unit="%" {...AX} />
              <Tooltip {...TT} />
              <Line dataKey="efficiency" stroke={C.orange} strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        {/* Output type volume */}
        <ChartCard title="Output Type Volume">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={outputVol} layout="vertical">
              <XAxis type="number" {...AX} />
              <YAxis dataKey="type" type="category" {...AX} width={90} />
              <Tooltip {...TT} />
              <Bar dataKey="count" fill={C.purple} radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        {/* Input type: created vs published */}
        <ChartCard title="Input Type: Created vs Published">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={inputVol}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2a2a2a" />
              <XAxis dataKey="type" {...AX} angle={-15} textAnchor="end" height={50} />
              <YAxis {...AX} />
              <Tooltip {...TT} /><Legend wrapperStyle={{ fontSize: 10 }} />
              <Bar dataKey="created" fill={C.indigo} radius={[2, 2, 0, 0]} />
              <Bar dataKey="published" fill={C.green} radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        {/* Language */}
        <ChartCard title="Language Breakdown">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={langData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2a2a2a" />
              <XAxis dataKey="language" {...AX} />
              <YAxis {...AX} />
              <Tooltip {...TT} /><Legend wrapperStyle={{ fontSize: 10 }} />
              <Bar dataKey="created" fill={C.blue} radius={[2, 2, 0, 0]} />
              <Bar dataKey="published" fill={C.green} radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        {/* Insights */}
        <ChartCard title="AI Insights">
          <div className="space-y-2 text-xs overflow-y-auto" style={{ height: 220 }}>
            {monthly.length === 0 && <p className="text-muted-foreground">Waiting for backend data…</p>}
            {anomalies.map((a, i) => (
              <div key={i} className="p-2 rounded bg-red-500/10 text-red-400">
                ⚠ Anomaly in {a.month}: {n(a.created_count).toLocaleString()} clips
              </div>
            ))}
            {(() => {
              const latest = monthly[monthly.length - 1];
              if (!latest) return null;
              const rate = n(latest.created_count) ? n(latest.published_count) / n(latest.created_count) * 100 : 0;
              return (
                <div className={`p-2 rounded ${rate < 5 ? "bg-red-500/10 text-red-400" : "bg-green-500/10 text-green-400"}`}>
                  Latest publish rate: {rate.toFixed(1)}%
                </div>
              );
            })()}
            {anomalies.length === 0 && monthly.length > 0 && (
              <div className="p-2 rounded bg-muted text-muted-foreground">No statistical anomalies detected this period.</div>
            )}
          </div>
        </ChartCard>

      </div>
    </DashboardLayout>
  );
}

// ── Sub-components ────────────────────────────────────────────────

function TrendCard({ title, data, color, growth, showComp }) {
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
      className="rounded-xl border bg-card p-5">
      <div className="flex justify-between mb-3">
        <h3 className="text-sm font-medium">{title}</h3>
        {growth != null && (
          <span className={`flex items-center text-xs px-2 py-0.5 rounded-full ${growth >= 0 ? "text-green-500 bg-green-500/10" : "text-red-500 bg-red-500/10"
            }`}>
            {growth >= 0 ? <ArrowUp className="h-3 w-3 mr-0.5" /> : <ArrowDown className="h-3 w-3 mr-0.5" />}
            {Math.abs(growth).toFixed(1)}%
          </span>
        )}
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#2a2a2a" />
          <XAxis dataKey="month" {...AX} />
          <YAxis {...AX} />
          <Tooltip {...TT} />
          <Line type="monotone" dataKey="current" stroke={color} strokeWidth={2} dot={false} name="Current" />
          {showComp && <Line type="monotone" dataKey="previous" stroke={color} strokeWidth={1} strokeDasharray="4 4" dot={false} name="Previous" opacity={0.4} />}
        </LineChart>
      </ResponsiveContainer>
    </motion.div>
  );
}

function ChartCard({ title, children }) {
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
      className="rounded-xl border bg-card p-5">
      <h3 className="mb-3 text-sm font-medium">{title}</h3>
      {children}
    </motion.div>
  );
}