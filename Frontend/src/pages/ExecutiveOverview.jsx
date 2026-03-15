import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { KpiCard } from "@/components/kpi-cards/KpiCard";

import {
UploadCloud,
Settings,
FileCheck,
Percent,
Clock,
XCircle
} from "lucide-react";

import { motion } from "framer-motion";

import {
LineChart,
Line,
XAxis,
YAxis,
CartesianGrid,
Tooltip,
Legend,
ResponsiveContainer,
BarChart,
Bar,
ScatterChart,
Scatter
} from "recharts";

export default function ExecutiveOverview() {

/* =========================
API CALLS
========================= */

const { data: summary } = useQuery({
queryKey: ["summary"],
queryFn: async () => {
const res = await fetch("http://localhost:8000/api/summary");
if (!res.ok) return {};
return res.json();
}
});

const { data: monthlyData = [] } = useQuery({
queryKey: ["monthly"],
queryFn: async () => {
const res = await fetch("http://localhost:8000/api/monthly");
if (!res.ok) return [];
return res.json();
}
});

const { data: userData = [] } = useQuery({
queryKey: ["users"],
queryFn: async () => {
const res = await fetch("http://localhost:8000/api/users");
if (!res.ok) return [];
return res.json();
}
});

const { data: channelData = [] } = useQuery({
queryKey: ["channels"],
queryFn: async () => {
const res = await fetch("http://localhost:8000/api/channels");
if (!res.ok) return [];
return res.json();
}
});

const safeSummary = summary || {};

/* =========================
AI EFFICIENCY SCORE
========================= */

const aiEfficiencyScore = useMemo(() => {

const publish = safeSummary.global_publish_rate || 0;
const waste = 100 - (safeSummary.ai_compute_waste_rate || 0);
const multiplier = Math.min(
  (safeSummary.ai_content_multiplier || 0) * 20,
  100
);

const score =
  publish * 0.4 +
  waste * 0.3 +
  multiplier * 0.3;

return Number(score.toFixed(1));

}, [safeSummary]);

const insights = useMemo(() => {

  const insights = [];

  const waste = safeSummary.ai_compute_waste_rate || 0;
  const publish = safeSummary.global_publish_rate || 0;
  const multiplier = safeSummary.ai_content_multiplier || 0;

  if (waste > 90) {
    insights.push(`AI compute waste is critically high (${waste.toFixed(1)}%).`);
  }

  if (publish < 5) {
    insights.push(`Only ${publish.toFixed(2)}% of generated clips are published.`);
  }

  if (multiplier > 3) {
    insights.push(`AI pipeline multiplies content ${multiplier.toFixed(2)}×.`);
  }

  if ((safeSummary.dead_channel_pct || 0) > 50) {
    insights.push(
      `${safeSummary.dead_channel_pct}% of channels are inactive.`
    );
  }

  if ((safeSummary.zero_value_users || 0) > 10) {
    insights.push(
      `${safeSummary.zero_value_users} users generate no published content.`
    );
  }

  return insights;

}, [safeSummary]);

/* =========================
KPI CARDS
========================= */

const metrics = [
{
title: "Uploaded Clips",
value: (safeSummary.total_uploaded || 0).toLocaleString(),
icon: UploadCloud
},
{
title: "AI Generated Clips",
value: (safeSummary.total_ai_generated_clips || 0).toLocaleString(),
icon: Settings
},
{
title: "Published Clips",
value: (safeSummary.total_published_clips || 0).toLocaleString(),
icon: FileCheck
},
{
title: "Publish Rate",
value: `${Number(safeSummary.global_publish_rate || 0).toFixed(2)}%`,
icon: Percent
},
{
title: "Compute Waste",
value: `${Number(safeSummary.ai_compute_waste_rate || 0).toFixed(2)}%`,
icon: XCircle
},
{
title: "Compute Hours",
value: `${Number(safeSummary.total_server_compute_hrs || 0).toFixed(1)} hrs`,
icon: Clock
}
];

/* =========================
MONTHLY PIPELINE DATA
========================= */

const pipelineTrend = monthlyData.map(m => ({
month: m.month || "Unknown",
uploaded: m.uploaded_count || 0,
generated: m.created_count || 0,
published: m.published_count || 0
}));

const durationTrend = monthlyData.map(m => ({
month: m.month || "Unknown",
uploaded: (m.uploaded_mins || 0) / 60,
generated: (m.created_mins || 0) / 60,
published: (m.published_mins || 0) / 60
}));

const publishTrend = monthlyData.map(m => ({
month: m.month || "Unknown",
rate: m.publish_rate || 0
}));

const workloadData = monthlyData.map(m => ({
month: m.month || "Unknown",
clips: m.uploaded_count || 0
}));

/* =========================
FUNNEL
========================= */

const funnelData = [
{ stage: "Uploaded", value: safeSummary.total_uploaded || 0 },
{ stage: "Generated", value: safeSummary.total_ai_generated_clips || 0 },
{ stage: "Published", value: safeSummary.total_published_clips || 0 }
];

/* =========================
COMPUTE WASTE
========================= */

const wasteData = [
{
name: "Published",
value: safeSummary.total_published_clips || 0
},
{
name: "Wasted",
value:
(safeSummary.total_ai_generated_clips || 0) -
(safeSummary.total_published_clips || 0)
}
];

/* =========================
USER EFFICIENCY
========================= */

const efficiencyScatter = userData.map(u => ({
compute: (u.created_mins || 0) / 60,
rate: u.publish_rate || 0,
name: u.user_name
}));

const topUsers = [...userData]
.sort((a,b)=> (b.created_mins||0)-(a.created_mins||0))
.slice(0,10)
.map(u=>({
name: u.user_name,
compute: (u.created_mins||0)/60
}));

/* =========================
CHANNEL WASTE
========================= */

const channelWaste = channelData.map(c => ({
name: c.channel_name,
waste: Math.max(
(c.created_count || 0) -
(c.published_count || 0),
0
)
}));

/* =========================
UI
========================= */

return ( <DashboardLayout title="Executive Overview">

  <div className="grid grid-cols-[repeat(auto-fill,minmax(230px,1fr))] gap-4">
    {metrics.map(m => (
      <KpiCard
        key={m.title}
        title={m.title}
        value={m.value}
        icon={m.icon}
      />
    ))}
  </div>

  <div className="mt-8 grid grid-cols-1 lg:grid-cols-3 gap-4">

    <ChartCard title="AI Efficiency Score">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={[{ name:"Score", value: aiEfficiencyScore }]}>
          <XAxis dataKey="name"/>
          <YAxis domain={[0,100]}/>
          <Tooltip/>
          <Bar dataKey="value" fill="hsl(var(--chart-3))"/>
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>

    <ChartCard title="AI Pipeline Funnel">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={funnelData} layout="vertical">
          <XAxis type="number"/>
          <YAxis type="category" dataKey="stage"/>
          <Tooltip/>
          <Bar dataKey="value" fill="hsl(var(--chart-1))"/>
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>

    <ChartCard title="AI Compute Waste">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={wasteData}>
          <XAxis dataKey="name"/>
          <YAxis/>
          <Tooltip/>
          <Bar dataKey="value" fill="hsl(var(--chart-4))"/>
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>

  </div>
  <ChartCard title="AI Insights">

  <div className="space-y-3">

  {insights.length === 0 && (
  <p className="text-sm text-muted-foreground">
  No major anomalies detected in the AI pipeline.
  </p>
  )}

  {insights.map((i, index) => (

  <div
  key={index}
  className="p-3 rounded-lg bg-muted text-sm"
  >
  {i}
  </div>

  ))}

  </div>

  </ChartCard>

  <div className="mt-8 grid grid-cols-1 lg:grid-cols-2 gap-4">

    <ChartCard title="Pipeline Trend">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={pipelineTrend}>
          <CartesianGrid strokeDasharray="3 3"/>
          <XAxis dataKey="month"/>
          <YAxis/>
          <Tooltip/>
          <Legend/>
          <Line type="monotone" dataKey="uploaded" stroke="hsl(var(--chart-2))"/>
          <Line type="monotone" dataKey="generated" stroke="hsl(var(--chart-3))"/>
          <Line type="monotone" dataKey="published" stroke="hsl(var(--chart-1))"/>
        </LineChart>
      </ResponsiveContainer>
    </ChartCard>

    <ChartCard title="Duration Trend">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={durationTrend}>
          <CartesianGrid strokeDasharray="3 3"/>
          <XAxis dataKey="month"/>
          <YAxis/>
          <Tooltip/>
          <Legend/>
          <Line type="monotone" dataKey="uploaded" stroke="hsl(var(--chart-2))"/>
          <Line type="monotone" dataKey="generated" stroke="hsl(var(--chart-3))"/>
          <Line type="monotone" dataKey="published" stroke="hsl(var(--chart-1))"/>
        </LineChart>
      </ResponsiveContainer>
    </ChartCard>

    <ChartCard title="Publish Rate Trend">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={publishTrend}>
          <CartesianGrid strokeDasharray="3 3"/>
          <XAxis dataKey="month"/>
          <YAxis unit="%"/>
          <Tooltip/>
          <Line type="monotone" dataKey="rate" stroke="hsl(var(--chart-1))"/>
        </LineChart>
      </ResponsiveContainer>
    </ChartCard>

    <ChartCard title="Monthly Workload">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={workloadData}>
          <CartesianGrid strokeDasharray="3 3"/>
          <XAxis dataKey="month"/>
          <YAxis/>
          <Tooltip/>
          <Bar dataKey="clips" fill="hsl(var(--chart-2))"/>
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>

    <ChartCard title="User Efficiency">
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart>
          <XAxis type="number" dataKey="compute" name="Compute Hours"/>
          <YAxis type="number" dataKey="rate" name="Publish Rate"/>
          <Tooltip cursor={{ strokeDasharray:"3 3" }}/>
          <Scatter data={efficiencyScatter} fill="hsl(var(--chart-5))"/>
        </ScatterChart>
      </ResponsiveContainer>
    </ChartCard>

    <ChartCard title="Compute Waste by Channel">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={channelWaste}>
          <XAxis dataKey="name"/>
          <YAxis/>
          <Tooltip/>
          <Bar dataKey="waste" fill="hsl(var(--chart-4))"/>
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>

    <ChartCard title="Top Users by Compute">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={topUsers}>
          <XAxis dataKey="name"/>
          <YAxis/>
          <Tooltip/>
          <Bar dataKey="compute" fill="hsl(var(--chart-3))"/>
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>

  </div>

</DashboardLayout>


);
}

/* =========================
CHART CARD
========================= */

function ChartCard({ title, children }) {

return (
<motion.div
initial={{ opacity:0,y:10 }}
animate={{ opacity:1,y:0 }}
transition={{ duration:0.4 }}
className="rounded-xl border bg-card p-6"
> <h3 className="mb-4 text-sm font-semibold">{title}</h3> <div className="h-[260px]">{children}</div>
</motion.div>
);

}
