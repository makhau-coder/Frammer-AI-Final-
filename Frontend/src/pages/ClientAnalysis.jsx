import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { DashboardLayout } from "@/components/layout/DashboardLayout";

import {
BarChart,
Bar,
XAxis,
YAxis,
Tooltip,
ResponsiveContainer,
CartesianGrid,
Legend,
PieChart,
Pie,
Cell,
ScatterChart,
Scatter
} from "recharts";

import {
Table,
TableBody,
TableCell,
TableHead,
TableHeader,
TableRow,
} from "@/components/ui/table";

const API = "http://localhost:8000/api";

const fetchData = async (endpoint) => {
const res = await fetch(`${API}/${endpoint}`);
if (!res.ok) throw new Error("API error");
return res.json();
};

export default function ClientAnalysis() {

const { data: channels = [], isLoading: channelsLoading } = useQuery({
queryKey: ["channels"],
queryFn: () => fetchData("channels"),
});

const { data: users = [], isLoading: usersLoading } = useQuery({
queryKey: ["users"],
queryFn: () => fetchData("users"),
});

const { data: platforms = [], isLoading: platformsLoading } = useQuery({
queryKey: ["platforms"],
queryFn: () => fetchData("publishing-platforms"),
});

const loading = channelsLoading || usersLoading || platformsLoading;

const channelData = useMemo(() => {
return channels.map((c) => ({
name: c.channel_name || "Unknown",
processed: c.created_count || 0,
published: c.published_count || 0,
publishRate: c.publish_rate || 0
}))
.sort((a,b)=>b.processed-a.processed);
},[channels]);

const userData = useMemo(()=>{
return users.map(u=>({
name: u.user_name || "Unknown",
uploaded: u.uploaded_count || 0,
processed: u.created_count || 0,
published: u.published_count || 0
}))
.sort((a,b)=>b.uploaded-a.uploaded)
.slice(0,10);
},[users]);

const platformData = useMemo(()=>{

const grouped = {};

platforms.forEach(p=>{
const key = p.platform || "Unknown";
grouped[key] = (grouped[key] || 0) + (p.publish_count || 0);
});

return Object.entries(grouped).map(([name,value])=>({name,value}));

},[platforms]);

const topChannels = channelData.slice(0,10);

const tooltipStyle = {
  backgroundColor: "#ffffff",
  border: "1px solid #e5e7eb",
  borderRadius: 8,
  fontSize: 12,
  color: "#111827"
};


const colors = [
"#6366f1",
"#06b6d4",
"#22c55e",
"#f59e0b",
"#ef4444",
"#8b5cf6"
];

if(loading){
return(
<DashboardLayout title="Client / Channel / User Analysis">
<div className="p-10 text-center text-muted-foreground">
Loading analytics...
</div>
</DashboardLayout>
)
}

return(

<DashboardLayout title="Client / Channel / User Analysis">

{/* KPI CARDS */}

<div className="grid grid-cols-3 gap-4 mb-6">

<div className="p-4 rounded-lg border bg-card">
<p className="text-xs text-muted-foreground">Total Channels</p>
<p className="text-2xl font-semibold">{channels.length}</p>
</div>

<div className="p-4 rounded-lg border bg-card">
<p className="text-xs text-muted-foreground">Total Users</p>
<p className="text-2xl font-semibold">{users.length}</p>
</div>

<div className="p-4 rounded-lg border bg-card">
<p className="text-xs text-muted-foreground">Platforms</p>
<p className="text-2xl font-semibold">{platformData.length}</p>
</div>

</div>

<div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

{/* PLATFORM BAR */}

<div className="rounded-lg border bg-card p-4">

<h3 className="mb-3 text-sm font-medium">
Videos Published by Platform
</h3>

<ResponsiveContainer width="100%" height={260}>

<BarChart data={platformData} layout="vertical">

<CartesianGrid strokeDasharray="3 3"/>

<XAxis type="number"/>

<YAxis dataKey="name" type="category"/>

<Tooltip contentStyle={tooltipStyle}/>

<Bar dataKey="value" fill="#6366f1"/>

</BarChart>

</ResponsiveContainer>

</div>

{/* PLATFORM PIE */}

<div className="rounded-lg border bg-card p-4">

<h3 className="mb-3 text-sm font-medium">
Platform Distribution
</h3>

<ResponsiveContainer width="100%" height={260}>

<PieChart>

<Pie
  data={platformData}
  dataKey="value"
  nameKey="name"
  outerRadius={90}
  label={{ fill: "#1ac28d", fontSize: 12 }}
>

{platformData.map((entry,index)=>(
  <Cell
    key={index}
    fill={colors[index % colors.length]}
  />
))}

</Pie>

<Tooltip contentStyle={tooltipStyle}/>
<Legend/>

</PieChart>


</ResponsiveContainer>

</div>

{/* CHANNEL PROCESSED VS PUBLISHED */}

<div className="rounded-lg border bg-card p-4">

<h3 className="mb-3 text-sm font-medium">
Channels: Processed vs Published
</h3>

<ResponsiveContainer width="100%" height={260}>

<BarChart data={channelData.slice(0,8)}>

<CartesianGrid strokeDasharray="3 3"/>

<XAxis dataKey="name" angle={-20} textAnchor="end" height={50}/>

<YAxis/>

<Tooltip contentStyle={tooltipStyle}/>

<Legend/>

<Bar dataKey="processed" fill="#06b6d4"/>

<Bar dataKey="published" fill="#22c55e"/>

</BarChart>

</ResponsiveContainer>

</div>

{/* CHANNEL PUBLISH RATE */}

<div className="rounded-lg border bg-card p-4">

<h3 className="mb-3 text-sm font-medium">
Channel Publish Rate
</h3>

<ResponsiveContainer width="100%" height={260}>

<BarChart data={channelData.slice(0,10)}>

<CartesianGrid strokeDasharray="3 3"/>

<XAxis dataKey="name" angle={-20} textAnchor="end" height={50}/>

<YAxis/>

<Tooltip contentStyle={tooltipStyle}/>

<Bar dataKey="publishRate" fill="#f59e0b"/>

</BarChart>

</ResponsiveContainer>

</div>

{/* USER PRODUCTIVITY */}

<div className="rounded-lg border bg-card p-4">

<h3 className="mb-3 text-sm font-medium">
User Productivity
</h3>

<ResponsiveContainer width="100%" height={260}>

<BarChart data={userData}>

<CartesianGrid strokeDasharray="3 3"/>

<XAxis dataKey="name" angle={-20} textAnchor="end" height={50}/>

<YAxis/>

<Tooltip contentStyle={tooltipStyle}/>

<Legend/>

<Bar dataKey="uploaded" fill="#6366f1"/>

<Bar dataKey="published" fill="#22c55e"/>

</BarChart>

</ResponsiveContainer>

</div>

{/* CHANNEL EFFICIENCY */}

<div className="rounded-lg border bg-card p-4">

<h3 className="mb-3 text-sm font-medium">
Channel Efficiency
</h3>

<ResponsiveContainer width="100%" height={260}>

<ScatterChart>

<CartesianGrid/>

<XAxis dataKey="processed"/>

<YAxis dataKey="published"/>

<Tooltip cursor={{strokeDasharray:"3 3"}}/>

<Scatter data={channelData} fill="#6366f1"/>

</ScatterChart>

</ResponsiveContainer>

</div>

{/* TOP USERS */}

<div className="rounded-lg border bg-card p-4">

<h3 className="mb-3 text-sm font-medium">
Top 10 Users
</h3>

<div className="space-y-2">

{userData.map((u,i)=>(
<div key={i} className="flex items-center gap-3">

<span className="w-5 text-xs text-muted-foreground text-right">
{i+1}
</span>

<span className="flex-1 text-sm truncate">
{u.name}
</span>

<div className="w-32 h-2 rounded-full bg-secondary overflow-hidden">

<div
className="h-full bg-accent"
style={{
width:`${(u.uploaded/(userData[0]?.uploaded||1))*100}%`
}}
/>

</div>

<span className="text-xs text-muted-foreground w-8 text-right">
{u.uploaded}
</span>

</div>
))}

</div>

</div>

{/* CHANNEL TABLE */}

<motion.div
initial={{opacity:0,y:12}}
animate={{opacity:1,y:0}}
className="rounded-lg border bg-card p-4"
>

<h3 className="mb-3 text-sm font-medium">
Top Channels by Usage
</h3>

<div className="overflow-hidden rounded-md border">

<Table>

<TableHeader>

<TableRow>

<TableHead>Channel</TableHead>

<TableHead className="text-right">
Processed
</TableHead>

<TableHead className="text-right">
Published
</TableHead>

<TableHead className="text-right">
Rate
</TableHead>

</TableRow>

</TableHeader>

<TableBody>

{topChannels.map((c)=>(
<TableRow key={c.name}>

<TableCell className="text-xs font-medium">
{c.name}
</TableCell>

<TableCell className="text-right text-xs">
{c.processed}
</TableCell>

<TableCell className="text-right text-xs">
{c.published}
</TableCell>

<TableCell className="text-right text-xs">
{c.publishRate}%
</TableCell>

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


