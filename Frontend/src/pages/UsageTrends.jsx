import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { DashboardLayout } from "@/components/layout/DashboardLayout";

import {
LineChart,
Line,
XAxis,
YAxis,
Tooltip,
ResponsiveContainer,
BarChart,
Bar,
CartesianGrid
} from "recharts";

import { ArrowUp, ArrowDown, GitCompare } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function UsageTrends() {

const [showComparison,setShowComparison] = useState(false)

/* =============================
FETCH DATA
============================= */

const {data:monthlyData=[],isLoading:loadingMonthly} = useQuery({
queryKey:["monthlyTrends"],
queryFn:async()=>{
const res = await fetch("http://localhost:8000/api/monthly")
if(!res.ok) return []
return res.json()
}
})

const {data:outputTypesData=[],isLoading:loadingOutputTypes} = useQuery({
queryKey:["outputTypes"],
queryFn:async()=>{
const res = await fetch("http://localhost:8000/api/output-types")
if(!res.ok) return []
return res.json()
}
})

const safeMonthly = Array.isArray(monthlyData) ? monthlyData : []
const safeOutputTypes = Array.isArray(outputTypesData) ? outputTypesData : []

/* =============================
PEAK MONTH
============================= */

const peakMonth = useMemo(()=>{

if(!safeMonthly.length) return null

return safeMonthly.reduce((max,curr)=>
(curr.created_count||0)>(max.created_count||0)?curr:max
)

},[safeMonthly])

/* =============================
GROWTH CALCULATION
============================= */

const getGrowth = key =>{

if(safeMonthly.length<2) return null

const curr = safeMonthly[safeMonthly.length-1][key]||0
const prev = safeMonthly[safeMonthly.length-2][key]||0

if(prev===0) return 0

return ((curr-prev)/prev)*100
}

/* =============================
TREND DATA
============================= */

const mapMetric = (key,hours=false)=>

safeMonthly.map((m,i)=>{

const value = m[key]||0

const current = hours
? Number((value/60).toFixed(1))
: value

let previous=null

if(showComparison && safeMonthly[i-1]){

const prev = safeMonthly[i-1][key]||0

previous = hours
? Number((prev/60).toFixed(1))
: prev
}

return{
month:m.month,
current,
previous
}

})

const uploadData = useMemo(()=>mapMetric("uploaded_count"),[safeMonthly,showComparison])
const processedData = useMemo(()=>mapMetric("created_count"),[safeMonthly,showComparison])
const publishedData = useMemo(()=>mapMetric("published_count"),[safeMonthly,showComparison])
const hoursData = useMemo(()=>mapMetric("created_mins",true),[safeMonthly,showComparison])

/* =============================
PIPELINE CONVERSION
============================= */

const conversionData = useMemo(()=>{

return safeMonthly.map(m=>{

const upload = m.uploaded_count||0
const created = m.created_count||0
const published = m.published_count||0

return{
month:m.month,
upload_to_created:upload?(created/upload)*100:0,
created_to_publish:created?(published/created)*100:0
}

})

},[safeMonthly])

/* =============================
COMPUTE EFFICIENCY
============================= */

const efficiencyData = useMemo(()=>{

return safeMonthly.map(m=>{

const created = m.created_mins||0
const published = m.published_mins||0

return{
month:m.month,
efficiency:created?(published/created)*100:0
}

})

},[safeMonthly])

/* =============================
ANOMALY DETECTION
============================= */

const anomalies = useMemo(()=>{

if(safeMonthly.length<4) return []

const values = safeMonthly.map(m=>m.created_count||0)

const mean =
values.reduce((a,b)=>a+b,0)/values.length

const std =
Math.sqrt(values.reduce((s,v)=>s+(v-mean)**2,0)/values.length)

return safeMonthly.filter(
m=>Math.abs((m.created_count||0)-mean)>2*std
)

},[safeMonthly])

/* =============================
OUTPUT TYPES
============================= */

const outputVolumeStats = useMemo(()=>{

return safeOutputTypes
.map(o=>({
type:o.output_type,
count:o.created_count||0
}))
.sort((a,b)=>b.count-a.count)

},[safeOutputTypes])

/* =============================
AI INSIGHTS
============================= */

const insights = useMemo(()=>{

let list=[]

const latest = safeMonthly[safeMonthly.length-1]

if(!latest) return list

const publishRate =
latest.created_count
? (latest.published_count/latest.created_count)*100
:0

if(publishRate<5)
list.push("Publish conversion extremely low (<5%)")

if(anomalies.length)
list.push(`Workload anomaly detected in ${anomalies[0].month}`)

return list

},[safeMonthly,anomalies])

/* =============================
LOADING
============================= */

if(loadingMonthly || loadingOutputTypes){

return(
<DashboardLayout title="Usage & Trends">
<div className="py-10 text-center text-muted-foreground">
Loading trend data...
</div>
</DashboardLayout>
)

}

/* =============================
RENDER
============================= */

return(

<DashboardLayout title="Usage & Trends">

{peakMonth &&(

<div className="mb-4 text-xs text-muted-foreground">

Peak workload month:
<span className="ml-1 text-foreground font-medium">
{peakMonth.month} ({peakMonth.created_count} clips)
</span>

</div>

)}

<div className="mb-6 flex justify-end">

<Button
variant={showComparison?"default":"outline"}
size="sm"
onClick={()=>setShowComparison(!showComparison)}
className="gap-2"
>

<GitCompare className="h-4 w-4"/>

Compare

</Button>

</div>

<div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">

<TrendChart title="Uploads" data={uploadData} growth={getGrowth("uploaded_count")} color="chart-1"/>

<TrendChart title="Processed Videos" data={processedData} growth={getGrowth("created_count")} color="chart-2"/>

<TrendChart title="Published Videos" data={publishedData} growth={getGrowth("published_count")} color="chart-3"/>

<TrendChart title="Processing Hours" data={hoursData} growth={getGrowth("created_mins")} color="chart-4"/>

<ConversionChart data={conversionData}/>

<EfficiencyChart data={efficiencyData}/>

<OutputChart title="Output Type Volume" data={outputVolumeStats} metric="count"/>

<InsightsCard insights={insights}/>

</div>

</DashboardLayout>

)

}

/* =============================
REUSABLE COMPONENTS
============================= */

function TrendChart({title,data,growth,color}){

return(

<div className="rounded-xl border bg-card p-6 card-shadow">

<div className="flex justify-between mb-4">

<h3 className="text-sm font-medium">{title}</h3>

{growth!=null && <GrowthBadge growth={growth}/>}

</div>

<ResponsiveContainer width="100%" height={220}>

<LineChart data={data}>

<CartesianGrid strokeDasharray="3 3"/>

<XAxis dataKey="month"/>

<YAxis/>

<Tooltip/>

<Line type="monotone" dataKey="current" stroke={`hsl(var(--${color}))`} strokeWidth={2}/>

</LineChart>

</ResponsiveContainer>

</div>

)

}

function ConversionChart({data}){

return(

<div className="rounded-xl border bg-card p-6 card-shadow">

<h3 className="mb-4 text-sm font-medium">Pipeline Conversion</h3>

<ResponsiveContainer width="100%" height={220}>

<LineChart data={data}>

<CartesianGrid strokeDasharray="3 3"/>

<XAxis dataKey="month"/>

<YAxis unit="%"/>

<Tooltip/>

<Line dataKey="upload_to_created" stroke="hsl(var(--chart-2))"/>

<Line dataKey="created_to_publish" stroke="hsl(var(--chart-3))"/>

</LineChart>

</ResponsiveContainer>

</div>

)

}

function EfficiencyChart({data}){

return(

<div className="rounded-xl border bg-card p-6 card-shadow">

<h3 className="mb-4 text-sm font-medium">Compute Efficiency</h3>

<ResponsiveContainer width="100%" height={220}>

<LineChart data={data}>

<CartesianGrid strokeDasharray="3 3"/>

<XAxis dataKey="month"/>

<YAxis unit="%"/>

<Tooltip/>

<Line dataKey="efficiency" stroke="hsl(var(--chart-4))"/>

</LineChart>

</ResponsiveContainer>

</div>

)

}

function OutputChart({title,data,metric}){

return(

<div className="rounded-xl border bg-card p-6 card-shadow">

<h3 className="mb-4 text-sm font-medium">{title}</h3>

<ResponsiveContainer width="100%" height={220}>

<BarChart data={data} layout="vertical">

<XAxis type="number"/>

<YAxis dataKey="type" type="category"/>

<Tooltip/>

<Bar dataKey={metric} fill="hsl(var(--chart-5))"/>

</BarChart>

</ResponsiveContainer>

</div>

)

}

function InsightsCard({insights}){

return(

<div className="rounded-xl border bg-card p-6 card-shadow">

<h3 className="mb-4 text-sm font-medium">AI Insights</h3>

<div className="space-y-2 text-xs">

{insights.length===0 && <div>No anomalies detected</div>}

{insights.map((i,index)=>(
<div key={index} className="p-2 rounded bg-muted">
{i}
</div>
))}

</div>

</div>

)

}

function GrowthBadge({growth}){

const positive=growth>=0
const Icon=positive?ArrowUp:ArrowDown

return(

<div className={`flex items-center text-xs px-2 py-1 rounded-full ${
positive?"text-green-500 bg-green-500/10":"text-red-500 bg-red-500/10"
}`}>

<Icon className="h-3 w-3 mr-1"/>

{Math.abs(growth).toFixed(1)}%

</div>

)

}