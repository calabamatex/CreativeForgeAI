import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { TechnicalMetrics } from "../../api/types";

/** Each entry pairs a campaign name with its TechnicalMetrics. */
export interface TechnicalEntry {
  campaignName: string;
  metrics: TechnicalMetrics;
}

interface Props {
  data: TechnicalEntry[];
}

const COLORS = {
  blue: "#3b82f6",
  green: "#10b981",
  amber: "#f59e0b",
  red: "#ef4444",
  indigo: "#6366f1",
};

const PIE_COLORS = [COLORS.green, COLORS.red];

// ---------------------------------------------------------------------------
// Generation Times Bar Chart
// ---------------------------------------------------------------------------

function GenerationTimesChart({ data }: Props) {
  const chartData = data.map((d) => ({
    name: truncate(d.campaignName, 20),
    "Avg Gen Time (s)": d.metrics.average_generation_time,
    "Total Gen Time (s)": d.metrics.total_generation_time,
  }));

  return (
    <div>
      <h3 className="text-sm font-semibold text-gray-700 mb-3">
        Generation Times per Campaign
      </h3>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis dataKey="name" tick={{ fontSize: 12 }} />
          <YAxis tick={{ fontSize: 12 }} />
          <Tooltip
            contentStyle={{
              borderRadius: "8px",
              border: "1px solid #e5e7eb",
              fontSize: "13px",
            }}
          />
          <Legend wrapperStyle={{ fontSize: "13px" }} />
          <Bar dataKey="Avg Gen Time (s)" fill={COLORS.blue} radius={[4, 4, 0, 0]} />
          <Bar dataKey="Total Gen Time (s)" fill={COLORS.green} radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ---------------------------------------------------------------------------
// API Latency / Call Count Line Chart
// ---------------------------------------------------------------------------

function ApiCallsChart({ data }: Props) {
  const chartData = data.map((d) => ({
    name: truncate(d.campaignName, 15),
    "API Calls": d.metrics.total_api_calls,
    "Assets Generated": d.metrics.total_assets_generated,
  }));

  return (
    <div>
      <h3 className="text-sm font-semibold text-gray-700 mb-3">
        API Calls and Assets Generated
      </h3>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis dataKey="name" tick={{ fontSize: 12 }} />
          <YAxis tick={{ fontSize: 12 }} />
          <Tooltip
            contentStyle={{
              borderRadius: "8px",
              border: "1px solid #e5e7eb",
              fontSize: "13px",
            }}
          />
          <Legend wrapperStyle={{ fontSize: "13px" }} />
          <Line
            type="monotone"
            dataKey="API Calls"
            stroke={COLORS.indigo}
            strokeWidth={2}
            dot={{ r: 4 }}
            activeDot={{ r: 6 }}
          />
          <Line
            type="monotone"
            dataKey="Assets Generated"
            stroke={COLORS.amber}
            strokeWidth={2}
            dot={{ r: 4 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Success / Failure Pie Chart
// ---------------------------------------------------------------------------

function SuccessRateChart({ data }: Props) {
  const avgSuccess =
    data.length > 0
      ? data.reduce((s, d) => s + d.metrics.api_success_rate, 0) / data.length
      : 0;
  const avgFailure = 100 - avgSuccess;

  const pieData = [
    { name: "Success", value: Math.round(avgSuccess * 10) / 10 },
    { name: "Failure", value: Math.round(avgFailure * 10) / 10 },
  ];

  return (
    <div>
      <h3 className="text-sm font-semibold text-gray-700 mb-3">
        Average Success / Failure Rate
      </h3>
      <div className="flex items-center gap-6">
        <ResponsiveContainer width="60%" height={250}>
          <PieChart>
            <Pie
              data={pieData}
              cx="50%"
              cy="50%"
              innerRadius={60}
              outerRadius={90}
              paddingAngle={3}
              dataKey="value"
              label={({ name, percent }) =>
                `${name} ${(percent * 100).toFixed(0)}%`
              }
            >
              {pieData.map((_entry, idx) => (
                <Cell key={idx} fill={PIE_COLORS[idx]} />
              ))}
            </Pie>
            <Tooltip />
          </PieChart>
        </ResponsiveContainer>
        <div className="flex-1 space-y-2 text-sm">
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-emerald-500" />
            <span className="text-gray-600">Success: {pieData[0].value}%</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-red-500" />
            <span className="text-gray-600">Failure: {pieData[1].value}%</span>
          </div>
          <p className="text-lg font-bold text-gray-900 pt-2">
            {avgSuccess.toFixed(1)}% success rate
          </p>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Combined Technical Metrics Panel
// ---------------------------------------------------------------------------

export default function TechnicalMetricsChart({ data }: Props) {
  if (data.length === 0) {
    return (
      <div className="text-center text-gray-500 py-12">
        No technical metrics data available.
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <GenerationTimesChart data={data} />
      <div className="border-t border-gray-100 pt-6">
        <ApiCallsChart data={data} />
      </div>
      <div className="border-t border-gray-100 pt-6">
        <SuccessRateChart data={data} />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function truncate(str: string, max: number): string {
  return str.length > max ? str.slice(0, max - 2) + "..." : str;
}
