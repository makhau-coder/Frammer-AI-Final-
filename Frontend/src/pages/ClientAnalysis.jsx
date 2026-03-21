import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, Legend, PieChart, Pie, Cell, ScatterChart, Scatter,
} from "recharts";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const API = "http://localhost:8000";
const TT = { contentStyle: { background: "#1a1b1e", border: "1px solid #333", borderRadius: 8, fontSize: 11, color: "#e0e0e0" } };
const AX = { tick: { fontSize: 10, fill: "#888" }, axisLine: { stroke: "#333" }, tickLine: false };
const PIE_COLORS = ["#6366f1", "#06b6d4", "#22c55e", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899"];
const n = (v) => Number(v || 0);

async function fetchArr(url) {
  try {
    const r = await fetch(API + url);
    if (!r.ok) { console.warn("[CA]", url, r.status); return []; }
    const d = await r.json();
    return Array.isArray(d) ? d : (Array.isArray(d?.data) ? d.data : []);
  } catch (e) { console.error("[CA]", url, e); return []; }
}

export default function ClientAnalysis() {

  const { data: channels = [] } = useQuery({ queryKey: ["channels100"], queryFn: () => fetchArr("/api/channels?page_size=100"), staleTime: 60000 });
  const { data: users = [] } = useQuery({ queryKey: ["users200"], queryFn: () => fetchArr("/api/users?limit=200"), staleTime: 60000 });
  const { data: platforms = [] } = useQuery({ queryKey: ["platforms"], queryFn: () => fetchArr("/api/publishing-platforms"), staleTime: 60000 });
  const { data: languages = [] } = useQuery({ queryKey: ["languages"], queryFn: () => fetchArr("/api/languages"), staleTime: 60000 });

  // Debug
  console.log("[CA] channels:", channels.length, channels[0]);
  console.log("[CA] platforms:", platforms.length, platforms[0]);  // should show: { channel_name, platform, publish_count, published_mins }

  // ── Channel data ──────────────────────────────────────────────────
  // cols: channel_name, uploaded_count, created_count, published_count,
  //       uploaded_mins, created_mins, published_mins, publish_rate, unpublished_gap
  const channelData = useMemo(() =>
    channels.map(c => ({
      name: String(c.channel_name || ""),
      uploaded: n(c.uploaded_count),
      processed: n(c.created_count),
      published: n(c.published_count),
      publishRate: parseFloat(n(c.publish_rate).toFixed(1)),
      gap: n(c.unpublished_gap) || Math.max(0, n(c.created_count) - n(c.published_count)),
    })).sort((a, b) => b.processed - a.processed),
    [channels]
  );

  // ── User data ─────────────────────────────────────────────────────
  // cols: user_name, uploaded_count, created_count, published_count, publish_rate
  const userData = useMemo(() =>
    users.map(u => ({
      name: String(u.user_name || ""),
      uploaded: n(u.uploaded_count),
      processed: n(u.created_count),
      published: n(u.published_count),
    })).sort((a, b) => b.uploaded - a.uploaded).slice(0, 10),
    [users]
  );

  // ── Platform data — VERIFIED field: publish_count (not published_count) ──
  // cols: channel_name, platform, publish_count, published_mins
  const platformData = useMemo(() => {
    const grouped = {};
    platforms.forEach(p => {
      const key = String(p.platform || "Unknown");
      // CRITICAL: field is publish_count, confirmed from parquet metadata
      grouped[key] = (grouped[key] || 0) + n(p.publish_count);
    });
    const result = Object.entries(grouped)
      .map(([name, value]) => ({ name, value }))
      .filter(d => d.value > 0)
      .sort((a, b) => b.value - a.value);
    console.log("[CA] platformData:", result);
    return result;
  }, [platforms]);

  // ── Language data ─────────────────────────────────────────────────
  const languageData = useMemo(() =>
    languages.map(l => ({
      language: String(l.language || ""),
      created: n(l.created_count),
      published: n(l.published_count),
      publishRate: parseFloat(n(l.publish_rate).toFixed(1)),
    })).sort((a, b) => b.created - a.created),
    [languages]
  );

  return (
    <DashboardLayout title="Client / Channel / User Analysis">

      {/* Summary KPIs */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <KpiBox label="Total Channels" value={channels.length} />
        <KpiBox label="Total Users" value={users.length} />
        <KpiBox label="Active Platforms" value={platformData.length} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

        {/* Platform bar */}
        <ChartBox title="Videos Published by Platform" insight="YouTube and Instagram typically dominate publishing. Channels concentrating on fewer platforms may achieve higher quality control and audience engagement.">
          {platformData.length === 0
            ? <NoData msg="No platform data. Check if /api/publishing-platforms is returning data." />
            : <ResponsiveContainer width="100%" height={260}>
              <BarChart data={platformData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#2a2a2a" />
                <XAxis type="number" {...AX} />
                <YAxis dataKey="name" type="category" {...AX} width={85} />
                <Tooltip {...TT} />
                <Bar dataKey="value" name="Published" fill="#6366f1" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          }
        </ChartBox>

        {/* Platform pie */}
        <ChartBox title="Platform Distribution" insight="A highly skewed distribution means the platform is heavily dependent on one or two channels. Diversifying distribution reduces risk and expands audience reach.">
          {platformData.length === 0
            ? <NoData />
            : <ResponsiveContainer width="100%" height={260}>
              <PieChart>
                <Pie
                  data={platformData} dataKey="value" nameKey="name"
                  cx="50%" cy="50%" outerRadius={100}
                  label={({ name, percent }) => percent > 0.05 ? `${name} ${(percent * 100).toFixed(0)}%` : ""}
                  labelLine={false}
                >
                  {platformData.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                </Pie>
                <Tooltip {...TT} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
              </PieChart>
            </ResponsiveContainer>
          }
        </ChartBox>

        {/* Channel: Processed vs Published */}
        <ChartBox title="Channels: Processed vs Published" insight="Channels with a large gap between processed and published clips represent the biggest AI compute waste. These channels need editorial throughput improvements.">
          {channelData.length === 0
            ? <NoData />
            : <ResponsiveContainer width="100%" height={260}>
              <BarChart data={channelData.slice(0, 8)}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a2a2a" />
                <XAxis dataKey="name" {...AX} angle={-20} textAnchor="end" height={50} />
                <YAxis {...AX} />
                <Tooltip {...TT} /><Legend wrapperStyle={{ fontSize: 10 }} />
                <Bar dataKey="processed" name="Processed" fill="#06b6d4" radius={[2, 2, 0, 0]} />
                <Bar dataKey="published" name="Published" fill="#22c55e" radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          }
        </ChartBox>

        {/* Channel publish rate */}
        <ChartBox title="Channel Publish Rate (%)" insight="High-performing channels demonstrate that quality editorial workflows are achievable. Low-rate channels should study the processes of high-rate channels.">
          {channelData.length === 0
            ? <NoData />
            : <ResponsiveContainer width="100%" height={260}>
              <BarChart data={channelData.slice(0, 10)}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a2a2a" />
                <XAxis dataKey="name" {...AX} angle={-20} textAnchor="end" height={50} />
                <YAxis unit="%" {...AX} />
                <Tooltip {...TT} />
                <Bar dataKey="publishRate" name="Publish %" fill="#f59e0b" radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          }
        </ChartBox>

        {/* Language */}
        <ChartBox title="Language: Created vs Published" insight="English content achieves a significantly higher publish rate than Hindi. This gap suggests language-specific editorial standards or reviewer availability issues.">
          {languageData.length === 0
            ? <NoData />
            : <ResponsiveContainer width="100%" height={260}>
              <BarChart data={languageData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a2a2a" />
                <XAxis dataKey="language" {...AX} />
                <YAxis {...AX} />
                <Tooltip {...TT} /><Legend wrapperStyle={{ fontSize: 10 }} />
                <Bar dataKey="created" name="Created" fill="#6366f1" radius={[2, 2, 0, 0]} />
                <Bar dataKey="published" name="Published" fill="#22c55e" radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          }
        </ChartBox>

        {/* User productivity */}
        <ChartBox title="Top 10 Users: Uploaded vs Published" insight="Users with many uploads but few publishes have a large backlog of unreviewed content. These users would benefit most from improved review processes or automation.">
          {userData.length === 0
            ? <NoData />
            : <ResponsiveContainer width="100%" height={260}>
              <BarChart data={userData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a2a2a" />
                <XAxis dataKey="name" {...AX} angle={-20} textAnchor="end" height={50} />
                <YAxis {...AX} />
                <Tooltip {...TT} /><Legend wrapperStyle={{ fontSize: 10 }} />
                <Bar dataKey="uploaded" name="Uploaded" fill="#6366f1" radius={[2, 2, 0, 0]} />
                <Bar dataKey="published" name="Published" fill="#22c55e" radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          }
        </ChartBox>

        {/* Channel efficiency scatter */}
        <ChartBox title="Channel Efficiency (Processed vs Published)" insight="Channels near the diagonal line are efficient — they publish a proportional share of what they generate. Outliers above the line have severe waste, those below undergenerate.">
          {channelData.length === 0
            ? <NoData />
            : <ResponsiveContainer width="100%" height={260}>
              <ScatterChart>
                <CartesianGrid stroke="#2a2a2a" />
                <XAxis type="number" dataKey="processed" name="Processed" {...AX} />
                <YAxis type="number" dataKey="published" name="Published" {...AX} />
                <Tooltip {...TT} cursor={{ strokeDasharray: "3 3" }} />
                <Scatter data={channelData} fill="#6366f1" />
              </ScatterChart>
            </ResponsiveContainer>
          }
        </ChartBox>

        {/* User leaderboard */}
        <div className="rounded-lg border bg-card p-4">
          <h3 className="mb-3 text-sm font-medium">Top 10 Users by Volume</h3>
          <div className="space-y-2">
            {userData.map((u, i) => (
              <div key={i} className="flex items-center gap-3">
                <span className="w-5 text-[11px] text-muted-foreground text-right">{i + 1}</span>
                <span className="flex-1 text-sm truncate">{u.name}</span>
                <div className="w-24 h-1.5 rounded-full bg-muted overflow-hidden">
                  <div className="h-full bg-primary"
                    style={{ width: `${userData[0]?.uploaded ? u.uploaded / userData[0].uploaded * 100 : 0}%` }} />
                </div>
                <span className="text-[11px] text-muted-foreground w-10 text-right">{u.uploaded}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Channel summary table */}
        <motion.div className="lg:col-span-2 rounded-lg border bg-card p-4">
          <h3 className="mb-3 text-sm font-medium">Channel Summary</h3>
          <div className="rounded-md border overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Channel</TableHead>
                  <TableHead className="text-right">Processed</TableHead>
                  <TableHead className="text-right">Published</TableHead>
                  <TableHead className="text-right">Gap</TableHead>
                  <TableHead className="text-right">Pub Rate</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {channelData.map(c => (
                  <TableRow key={c.name}>
                    <TableCell className="text-xs font-medium">{c.name}</TableCell>
                    <TableCell className="text-right text-xs">{c.processed.toLocaleString()}</TableCell>
                    <TableCell className="text-right text-xs">{c.published.toLocaleString()}</TableCell>
                    <TableCell className="text-right text-xs text-destructive">{c.gap.toLocaleString()}</TableCell>
                    <TableCell className="text-right text-xs">{c.publishRate}%</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </motion.div>

      </div>
    </DashboardLayout>
  );
}

function KpiBox({ label, value }) {
  return (
    <div className="p-4 rounded-lg border bg-card">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-2xl font-semibold mt-1">{value}</p>
    </div>
  );
}

function ChartBox({ title, insight, children }) {
  return (
    <div className="rounded-lg border bg-card p-4">
      <h3 className="mb-3 text-sm font-medium">{title}</h3>
      {children}
      {insight && (
        <div className="mt-3 pt-3 border-t border-border/40 flex gap-2 text-[11px] text-muted-foreground leading-relaxed">
          <span className="text-yellow-400 shrink-0">💡</span>
          <span>{insight}</span>
        </div>
      )}
    </div>
  );
}

function NoData({ msg = "No data — check backend is running" }) {
  return <div className="flex h-[260px] items-center justify-center text-sm text-muted-foreground">{msg}</div>;
}