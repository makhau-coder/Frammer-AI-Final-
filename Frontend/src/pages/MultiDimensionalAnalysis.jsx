import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Legend
} from "recharts";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "@/components/ui/select";
import { Lightbulb } from "lucide-react";


// Only supported dimension pairs
const dimensionPairs = [
  { label: "Channel × User", dim1: "channel", dim2: "user" },
  { label: "Channel × Platform", dim1: "channel", dim2: "platform" },
  { label: "User × Input Type", dim1: "user", dim2: "input_type" },
  { label: "User × Platform", dim1: "user", dim2: "platform" },
  { label: "User × Published Status", dim1: "user", dim2: "published_status" },
  { label: "Input Type × Platform", dim1: "input_type", dim2: "platform" },
  { label: "Input Type × Published Status", dim1: "input_type", dim2: "published_status" }
];


export default function MultiDimensionalAnalysis() {

  const [pairIndex, setPairIndex] = useState(1);

  const dim1 = dimensionPairs[pairIndex].dim1;
  const dim2 = dimensionPairs[pairIndex].dim2;

  const { data = [], isLoading } = useQuery({
    queryKey: ["multidimensional", dim1, dim2],
    queryFn: async () => {

      const res = await fetch(
        `http://localhost:8000/api/multidimensional?dim1=${dim1}&dim2=${dim2}`
      );

      if (!res.ok) throw new Error("API error");

      return res.json();
    }
  });


  // Build pivot structure
  const pivot = useMemo(() => {

    const map = {};
    const dim2Values = new Set();

    data.forEach(r => {

      const k1 = r[dim1];
      const k2 = r[dim2];

      dim2Values.add(k2);

      if (!map[k1]) map[k1] = {};

      map[k1][k2] = (map[k1][k2] || 0) + (r.publish_count || 0);

    });

    const dim2Arr = Array.from(dim2Values);

    const rows = Object.entries(map).map(([name, vals]) => ({
      name,
      ...vals
    }));

    return { rows, dim2Arr };

  }, [data, dim1, dim2]);


  // Top dimension chart
  const topData = useMemo(() => {

    return pivot.rows
      .map(r => ({
        name: r.name,
        total: pivot.dim2Arr.reduce((s, k) => s + (r[k] || 0), 0)
      }))
      .sort((a, b) => b.total - a.total)
      .slice(0, 10);

  }, [pivot]);


  // Duration aggregation
  const durationData = useMemo(() => {

    const map = {};

    data.forEach(r => {

      const key = r[dim1];

      if (!map[key]) map[key] = 0;

      map[key] += r.published_mins || 0;

    });

    return Object.entries(map).map(([name, mins]) => ({
      name,
      minutes: Number(mins.toFixed(2))
    }));

  }, [data, dim1]);


  const maxHeat = Math.max(...data.map(d => d.publish_count || 0), 1);


  // AI insights
  const insights = useMemo(() => {

    const arr = [];

    if (topData.length)
      arr.push(`${topData[0].name} has the highest publish volume (${topData[0].total} videos).`);

    if (durationData.length) {

      const best = [...durationData].sort((a, b) => b.minutes - a.minutes)[0];

      arr.push(`${best.name} has the longest published duration (${best.minutes} mins).`);
    }

    arr.push("Darker heatmap cells indicate stronger distribution relationships.");

    return arr;

  }, [topData, durationData]);


  const colors = [
    "#6366f1",
    "#10b981",
    "#f59e0b",
    "#ef4444",
    "#8b5cf6",
    "#06b6d4"
  ];


  if (isLoading)
    return (
      <DashboardLayout title="Multi-Dimensional Analysis">
        <div className="p-10 text-center text-muted-foreground">
          Loading multidimensional analytics...
        </div>
      </DashboardLayout>
    );


  return (
    <DashboardLayout title="Multi-Dimensional Analysis">


      {/* Pair selector */}

      <div className="mb-4 w-72">

        <label className="text-xs text-muted-foreground">
          Dimension Combination
        </label>

        <Select
          value={pairIndex.toString()}
          onValueChange={(v) => setPairIndex(Number(v))}
        >

          <SelectTrigger className="h-8 text-xs">
            <SelectValue />
          </SelectTrigger>

          <SelectContent>

            {dimensionPairs.map((p, i) => (
              <SelectItem key={i} value={i.toString()}>
                {p.label}
              </SelectItem>
            ))}

          </SelectContent>

        </Select>

      </div>


      {/* Charts */}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">


        {/* Stacked chart */}

        <div className="lg:col-span-2 rounded-lg border bg-card p-4">

          <h3 className="mb-3 text-sm font-medium">
            Publish Count by {dim1} × {dim2}
          </h3>

          <ResponsiveContainer width="100%" height={350}>
            <BarChart data={pivot.rows}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" angle={-15} textAnchor="end" height={60} />
              <YAxis />
              <Tooltip />
              <Legend />

              {pivot.dim2Arr.map((val, i) => (
                <Bar
                  key={val}
                  dataKey={val}
                  stackId="a"
                  fill={colors[i % colors.length]}
                />
              ))}

            </BarChart>
          </ResponsiveContainer>

        </div>


        {/* Insights */}

        <div className="rounded-lg border bg-card p-4">

          <div className="flex items-center gap-2 mb-3">
            <Lightbulb className="h-4 w-4 text-yellow-500" />
            <h3 className="text-sm font-medium">Insights</h3>
          </div>

          <div className="space-y-2">

            {insights.map((i, idx) => (
              <p key={idx} className="text-xs text-muted-foreground">
                💡 {i}
              </p>
            ))}

          </div>

        </div>


        {/* Top dimension */}

        <div className="rounded-lg border bg-card p-4 lg:col-span-3">

          <h3 className="mb-3 text-sm font-medium">
            Top {dim1} by Published Videos
          </h3>

          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={topData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip />
              <Bar dataKey="total" fill="#6366f1" />
            </BarChart>
          </ResponsiveContainer>

        </div>


        {/* Duration chart */}

        <div className="rounded-lg border bg-card p-4 lg:col-span-3">

          <h3 className="mb-3 text-sm font-medium">
            Published Duration by {dim1}
          </h3>

          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={durationData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip />
              <Bar dataKey="minutes" fill="#10b981" />
            </BarChart>
          </ResponsiveContainer>

        </div>

      </div>


      {/* Heatmap */}

      <div className="mt-4 rounded-lg border bg-card p-4 overflow-auto">

        <h3 className="mb-3 text-sm font-medium">
          Heatmap: {dim1} × {dim2}
        </h3>

        <table className="w-full text-xs">

          <thead>
            <tr>
              <th className="p-2 text-left">{dim1}</th>

              {pivot.dim2Arr.map(v => (
                <th key={v} className="p-2 text-center">{v}</th>
              ))}

            </tr>
          </thead>

          <tbody>

            {pivot.rows.map(row => (

              <tr key={row.name}>

                <td className="p-2 font-medium">{row.name}</td>

                {pivot.dim2Arr.map(v => {

                  const val = row[v] || 0;
                  const intensity = val / maxHeat;

                  return (
                    <td
                      key={v}
                      className="p-2 text-center"
                      style={{
                        backgroundColor: `rgba(99,102,241,${intensity})`
                      }}
                    >
                      {val}
                    </td>
                  );

                })}

              </tr>

            ))}

          </tbody>

        </table>

      </div>


    </DashboardLayout>
  );
}




