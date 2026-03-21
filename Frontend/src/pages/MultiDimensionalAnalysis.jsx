/**
 * src/pages/MultiDimensionalAnalysis.jsx
 *
 * FIXES:
 * 1. channel×platform uses publish_count (not published_count) — pivot now checks all field variants
 * 2. topData aggregation falls back to publish_count for channel×platform
 * 3. heatmap cell value uses correct field
 * 4. Uses api.chatStream from api.js for chatStream URL
 */

import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, Legend,
} from "recharts";
import {
  Select, SelectContent, SelectItem,
  SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Lightbulb } from "lucide-react";
import { api } from "@/lib/api";

const dimensionPairs = [
  { label: "Channel × User", dim1: "channel", dim2: "user" },
  { label: "Channel × Platform", dim1: "channel", dim2: "platform" },
  { label: "User × Input Type", dim1: "user", dim2: "input_type" },
  { label: "User × Platform", dim1: "user", dim2: "platform" },
  { label: "User × Published Status", dim1: "user", dim2: "published_status" },
  { label: "Input Type × Platform", dim1: "input_type", dim2: "platform" },
  { label: "Input Type × Published Status", dim1: "input_type", dim2: "published_status" },
];

const COLORS = ["#6366f1", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4", "#ec4899"];

// ─── Helper: get the "primary volume" field from a row regardless of naming ──
// Different cross parquets use different field names:
//   channel×user / user×* / input_type×* → created_count, published_count
//   channel×platform                     → publish_count, published_mins
function getVolume(row) {
  return (
    row.created_count ||
    row.published_count ||
    row.publish_count ||
    0
  );
}

function getPublished(row) {
  return (
    row.published_count ||
    row.publish_count ||
    0
  );
}

export default function MultiDimensionalAnalysis() {

  const [pairIndex, setPairIndex] = useState(0);
  const { dim1, dim2 } = dimensionPairs[pairIndex];

  const { data: response, isLoading, isError } = useQuery({
    queryKey: ["multidimensional", dim1, dim2],
    queryFn: () => api.multidim(dim1, dim2),
  });

  // API returns { dim1, dim2, row_count, columns, rows }
  const rows = response?.rows || [];

  /* ── Pivot for stacked bar ─────────────────────────────────────── */
  const pivot = useMemo(() => {
    const map = {};
    const dim2Values = new Set();

    rows.forEach(r => {
      const k1 = r[dim1];
      const k2 = r[dim2];
      if (!k1 || k1 === 0 || !k2 || k2 === 0) return;
      dim2Values.add(String(k2));
      if (!map[k1]) map[k1] = {};
      // FIX: use getPublished() which handles both publish_count and published_count
      map[k1][String(k2)] = (map[k1][String(k2)] || 0) + getPublished(r);
    });

    const dim2Arr = Array.from(dim2Values).slice(0, 10); // cap at 10 legend items
    const pivotRows = Object.entries(map)
      .map(([name, vals]) => ({ name, ...vals }))
      .sort((a, b) => {
        const aTotal = dim2Arr.reduce((s, k) => s + (a[k] || 0), 0);
        const bTotal = dim2Arr.reduce((s, k) => s + (b[k] || 0), 0);
        return bTotal - aTotal;
      })
      .slice(0, 15);

    return { rows: pivotRows, dim2Arr };
  }, [rows, dim1, dim2]);

  /* ── Top dim1 by volume (created OR publish_count) ──────────────── */
  const topData = useMemo(() => {
    const map = {};
    rows.forEach(r => {
      const k = r[dim1];
      if (!k) return;
      map[k] = (map[k] || 0) + getVolume(r);
    });
    return Object.entries(map)
      .map(([name, total]) => ({ name, total }))
      .filter(d => d.total > 0)
      .sort((a, b) => b.total - a.total)
      .slice(0, 12);
  }, [rows, dim1]);

  /* ── Publish rate by dim1 ──────────────────────────────────────── */
  const rateData = useMemo(() => {
    const createdMap = {};
    const publishedMap = {};
    rows.forEach(r => {
      const k = r[dim1];
      if (!k) return;
      // FIX: for channel×platform, use publish_count as both created and published
      const created = r.created_count || r.publish_count || 0;
      const published = r.published_count || r.publish_count || 0;
      createdMap[k] = (createdMap[k] || 0) + created;
      publishedMap[k] = (publishedMap[k] || 0) + published;
    });
    return Object.keys(createdMap)
      .map(name => ({
        name,
        publish_rate: createdMap[name]
          ? Number(((publishedMap[name] || 0) / createdMap[name] * 100).toFixed(1))
          : 0,
      }))
      .filter(d => d.publish_rate > 0)
      .sort((a, b) => b.publish_rate - a.publish_rate)
      .slice(0, 12);
  }, [rows, dim1]);

  /* ── Heatmap ────────────────────────────────────────────────────── */
  const maxHeat = Math.max(...rows.map(r => getPublished(r)), 1);

  /* ── Insights ────────────────────────────────────────────────────── */
  const insights = useMemo(() => {
    const arr = [];
    if (topData.length)
      arr.push(`${topData[0].name} leads in volume with ${topData[0].total.toLocaleString()} clips.`);
    if (rateData.length)
      arr.push(`${rateData[0].name} has the best publish rate: ${rateData[0].publish_rate}%.`);
    const worst = rateData[rateData.length - 1];
    if (worst && worst.publish_rate < 2 && rateData.length > 1)
      arr.push(`${worst.name} has near-zero publish rate — potential bottleneck.`);
    arr.push("Darker heatmap cells indicate stronger relationships between dimensions.");
    return arr;
  }, [topData, rateData]);

  /* ── Render ──────────────────────────────────────────────────────── */

  if (isLoading)
    return (
      <DashboardLayout title="Multi-Dimensional Analysis">
        <div className="p-10 text-center text-muted-foreground">Loading…</div>
      </DashboardLayout>
    );

  if (isError)
    return (
      <DashboardLayout title="Multi-Dimensional Analysis">
        <div className="p-10 text-center text-destructive">
          Failed to load data. Make sure the backend is running.
        </div>
      </DashboardLayout>
    );

  return (
    <DashboardLayout title="Multi-Dimensional Analysis">

      {/* Selector */}
      <div className="mb-6 w-72">
        <label className="text-xs text-muted-foreground mb-1 block">Dimension Combination</label>
        <Select value={pairIndex.toString()} onValueChange={v => setPairIndex(Number(v))}>
          <SelectTrigger className="h-9 text-sm"><SelectValue /></SelectTrigger>
          <SelectContent>
            {dimensionPairs.map((p, i) => (
              <SelectItem key={i} value={i.toString()}>{p.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <p className="mt-1 text-[11px] text-muted-foreground">
          {rows.length} combination{rows.length !== 1 ? "s" : ""} found
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

        {/* Stacked bar */}
        <div className="lg:col-span-2 rounded-lg border bg-card p-4">
          <h3 className="mb-3 text-sm font-medium">
            Published Clips: {dim1} × {dim2}
          </h3>
          {pivot.rows.length === 0 ? (
            <div className="h-[350px] flex items-center justify-center text-sm text-muted-foreground">
              No data for this combination.
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={350}>
              <BarChart data={pivot.rows}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" angle={-15} textAnchor="end" height={60} tick={{ fontSize: 10 }} />
                <YAxis tick={{ fontSize: 10 }} />
                <Tooltip />
                <Legend />
                {pivot.dim2Arr.map((val, i) => (
                  <Bar key={val} dataKey={val} stackId="a" fill={COLORS[i % COLORS.length]} />
                ))}
              </BarChart>
            </ResponsiveContainer>
          )}
          <div className="mt-3 pt-3 border-t border-border/40 flex gap-2 text-[11px] text-muted-foreground leading-relaxed">
            <span className="text-yellow-400 shrink-0">💡</span>
            <span>Stacked bars show how the top dimension is distributed across the second dimension. Tall single-color bars indicate concentration — the entity relies on one sub-category. Mixed-color bars indicate healthy diversification.</span>
          </div>
        </div>

        {/* Insights */}
        <div className="rounded-lg border bg-card p-4">
          <div className="flex items-center gap-2 mb-3">
            <Lightbulb className="h-4 w-4 text-yellow-500" />
            <h3 className="text-sm font-medium">Insights</h3>
          </div>
          <div className="space-y-2">
            {insights.map((ins, i) => (
              <p key={i} className="text-xs text-muted-foreground">💡 {ins}</p>
            ))}
          </div>

          {/* Summary stats */}
          {rows.length > 0 && (
            <div className="mt-4 space-y-2 border-t border-border pt-3">
              <div className="flex justify-between text-xs">
                <span className="text-muted-foreground">Total combinations</span>
                <span className="font-medium">{rows.length}</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-muted-foreground">Total published</span>
                <span className="font-medium">
                  {rows.reduce((s, r) => s + getPublished(r), 0).toLocaleString()}
                </span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-muted-foreground">Unique {dim1}</span>
                <span className="font-medium">
                  {new Set(rows.map(r => r[dim1])).size}
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Top by volume */}
        <div className="rounded-lg border bg-card p-4 lg:col-span-2">
          <h3 className="mb-3 text-sm font-medium">Top {dim1} by Volume</h3>
          {topData.length === 0 ? (
            <div className="h-[280px] flex items-center justify-center text-sm text-muted-foreground">No data</div>
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={topData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                <YAxis tick={{ fontSize: 10 }} />
                <Tooltip />
                <Bar dataKey="total" fill="#6366f1" />
              </BarChart>
            </ResponsiveContainer>
          )}
          <div className="mt-3 pt-3 border-t border-border/40 flex gap-2 text-[11px] text-muted-foreground">
            <span className="text-yellow-400 shrink-0">💡</span>
            <span>Volume leaders drive most of the platform output. If one entity dominates, consider whether workload is balanced or whether there is a dependency risk.</span>
          </div>
        </div>

        {/* Publish rate */}
        <div className="rounded-lg border bg-card p-4">
          <h3 className="mb-3 text-sm font-medium">Publish Rate by {dim1}</h3>
          {rateData.length === 0 ? (
            <div className="h-[280px] flex items-center justify-center text-sm text-muted-foreground">No data</div>
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={rateData} layout="vertical">
                <XAxis type="number" unit="%" tick={{ fontSize: 10 }} />
                <YAxis dataKey="name" type="category" width={85} tick={{ fontSize: 10 }} />
                <Tooltip />
                <Bar dataKey="publish_rate" fill="#10b981" />
              </BarChart>
            </ResponsiveContainer>
          )}
          <div className="mt-3 pt-3 border-t border-border/40 flex gap-2 text-[11px] text-muted-foreground">
            <span className="text-yellow-400 shrink-0">💡</span>
            <span>Publish rate leaders demonstrate what is achievable with good editorial workflow. Near-zero performers may need process review or could be candidates for consolidation.</span>
          </div>
        </div>

      </div>

      {/* Heatmap */}
      <div className="mt-4 rounded-lg border bg-card p-4 overflow-auto">
        <h3 className="mb-3 text-sm font-medium">
          Heatmap: {dim1} × {dim2} (published clips)
        </h3>
        <p className="mb-3 flex gap-1.5 text-[11px] text-muted-foreground">
          <span className="text-yellow-400">💡</span>
          Darker cells indicate stronger publishing relationships between the two dimensions. Dark rows show high-output entities across all categories. Dark columns indicate popular target categories.
        </p>
        {pivot.rows.length === 0 ? (
          <p className="text-xs text-muted-foreground">No data for this combination.</p>
        ) : (
          <table className="min-w-full text-xs border-collapse">
            <thead>
              <tr>
                <th className="p-2 text-left font-semibold border border-border/30">{dim1}</th>
                {pivot.dim2Arr.map(v => (
                  <th key={v} className="p-2 text-center font-semibold border border-border/30 min-w-[60px]">
                    {v}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {pivot.rows.map(row => (
                <tr key={row.name}>
                  <td className="p-2 font-medium border border-border/30 whitespace-nowrap">{row.name}</td>
                  {pivot.dim2Arr.map(v => {
                    const val = row[v] || 0;
                    const intensity = val / maxHeat;
                    return (
                      <td
                        key={v}
                        className="p-2 text-center border border-border/30"
                        title={`${row.name} × ${v}: ${val}`}
                        style={{ backgroundColor: `rgba(99,102,241,${Math.max(intensity, val > 0 ? 0.08 : 0)})` }}
                      >
                        {val > 0 ? val : "—"}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

    </DashboardLayout>
  );
}