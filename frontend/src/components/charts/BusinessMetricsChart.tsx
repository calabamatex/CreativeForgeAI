import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { BusinessMetrics, BusinessMetricsConfig } from "../../api/types";
import { DEFAULT_BASELINES } from "../../api/metrics";
import { AlertTriangle } from "lucide-react";

interface Props {
  data: BusinessMetrics[];
  /** Optional campaign names parallel to data, used for chart labels. */
  campaignNames?: string[];
  baselines?: BusinessMetricsConfig;
}

const COLORS = {
  blue: "#3b82f6",
  green: "#10b981",
  amber: "#f59e0b",
  red: "#ef4444",
  purple: "#8b5cf6",
};

// ---------------------------------------------------------------------------
// Baseline Warning Banner
// ---------------------------------------------------------------------------

function BaselineWarning({ baselines }: { baselines: BusinessMetricsConfig }) {
  return (
    <div className="flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 mb-6">
      <AlertTriangle className="mt-0.5 h-5 w-5 flex-shrink-0 text-amber-600" />
      <div className="text-sm">
        <p className="font-semibold text-amber-800">
          Estimates based on configured baselines
        </p>
        <p className="text-amber-700 mt-1">
          Business metrics are calculated using the following assumptions:
          <span className="font-medium">
            {" "}${baselines.manual_baseline_cost}/asset manual cost,{" "}
            {baselines.manual_baseline_hours}h/asset design time,{" "}
            ${baselines.hourly_rate}/hr designer rate,{" "}
            {baselines.manual_baseline_assets} assets/day baseline.
          </span>{" "}
          Adjust baselines in settings for more accurate estimates.
        </p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Cost Comparison Bar Chart
// ---------------------------------------------------------------------------

function CostComparisonChart({
  data,
  names,
}: {
  data: BusinessMetrics[];
  names: string[];
}) {
  const chartData = data.map((d, i) => {
    const label = names[i] ?? `Campaign ${i + 1}`;
    return {
      name: label.length > 20 ? label.slice(0, 18) + "..." : label,
      "Manual Cost ($)": d.estimated_manual_cost,
      "Automated Cost ($)": d.actual_generation_cost,
      "Savings ($)": d.cost_savings,
    };
  });

  return (
    <div>
      <h3 className="text-sm font-semibold text-gray-700 mb-3">
        Manual vs Automated Cost Comparison
      </h3>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis dataKey="name" tick={{ fontSize: 12 }} />
          <YAxis tick={{ fontSize: 12 }} tickFormatter={(v) => `$${v}`} />
          <Tooltip
            formatter={(value: number) => `$${value.toFixed(2)}`}
            contentStyle={{
              borderRadius: "8px",
              border: "1px solid #e5e7eb",
              fontSize: "13px",
            }}
          />
          <Legend wrapperStyle={{ fontSize: "13px" }} />
          <Bar dataKey="Manual Cost ($)" fill={COLORS.red} radius={[4, 4, 0, 0]} />
          <Bar dataKey="Automated Cost ($)" fill={COLORS.green} radius={[4, 4, 0, 0]} />
          <Bar dataKey="Savings ($)" fill={COLORS.blue} radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Cumulative Savings Line Chart
// ---------------------------------------------------------------------------

function CumulativeSavingsChart({
  data,
  names,
}: {
  data: BusinessMetrics[];
  names: string[];
}) {
  let cumulativeCost = 0;
  let cumulativeTime = 0;
  const chartData = data.map((d, i) => {
    cumulativeCost += d.cost_savings;
    cumulativeTime += d.time_savings_hours;
    const label = names[i] ?? `Campaign ${i + 1}`;
    return {
      name: label.length > 15 ? label.slice(0, 13) + "..." : label,
      "Cumulative Cost Savings ($)": Math.round(cumulativeCost * 100) / 100,
      "Cumulative Time Savings (h)": Math.round(cumulativeTime * 100) / 100,
    };
  });

  return (
    <div>
      <h3 className="text-sm font-semibold text-gray-700 mb-3">
        Cumulative Savings Over Time
      </h3>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis dataKey="name" tick={{ fontSize: 12 }} />
          <YAxis
            yAxisId="cost"
            tick={{ fontSize: 12 }}
            tickFormatter={(v) => `$${v}`}
          />
          <YAxis
            yAxisId="time"
            orientation="right"
            tick={{ fontSize: 12 }}
            tickFormatter={(v) => `${v}h`}
          />
          <Tooltip
            contentStyle={{
              borderRadius: "8px",
              border: "1px solid #e5e7eb",
              fontSize: "13px",
            }}
          />
          <Legend wrapperStyle={{ fontSize: "13px" }} />
          <Line
            yAxisId="cost"
            type="monotone"
            dataKey="Cumulative Cost Savings ($)"
            stroke={COLORS.green}
            strokeWidth={2}
            dot={{ r: 4 }}
            activeDot={{ r: 6 }}
          />
          <Line
            yAxisId="time"
            type="monotone"
            dataKey="Cumulative Time Savings (h)"
            stroke={COLORS.purple}
            strokeWidth={2}
            dot={{ r: 4 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Summary KPI Cards
// ---------------------------------------------------------------------------

function SummaryCards({ data }: { data: BusinessMetrics[] }) {
  const totalCostSavings = data.reduce((s, d) => s + d.cost_savings, 0);
  const totalTimeSavings = data.reduce((s, d) => s + d.time_savings_hours, 0);
  const avgRoi =
    data.length > 0
      ? data.reduce((s, d) => s + d.roi_percent, 0) / data.length
      : 0;
  const avgCostSavingsPercent =
    data.length > 0
      ? data.reduce((s, d) => s + d.cost_savings_percent, 0) / data.length
      : 0;

  const kpis = [
    {
      label: "Total Cost Savings",
      value: `$${totalCostSavings.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
      color: "text-green-600",
    },
    {
      label: "Total Time Saved",
      value: `${totalTimeSavings.toFixed(1)} hours`,
      color: "text-blue-600",
    },
    {
      label: "Avg ROI",
      value: `${avgRoi.toFixed(1)}%`,
      color: "text-purple-600",
    },
    {
      label: "Avg Cost Reduction",
      value: `${avgCostSavingsPercent.toFixed(1)}%`,
      color: "text-amber-600",
    },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      {kpis.map(({ label, value, color }) => (
        <div
          key={label}
          className="rounded-lg border border-gray-200 bg-white p-4 text-center"
        >
          <p className="text-xs text-gray-500 uppercase tracking-wide">{label}</p>
          <p className={`text-xl font-bold mt-1 ${color}`}>{value}</p>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Combined Business Metrics Panel
// ---------------------------------------------------------------------------

export default function BusinessMetricsChart({ data, campaignNames, baselines }: Props) {
  const config = baselines ?? DEFAULT_BASELINES;
  const names = campaignNames ?? data.map((_, i) => `Campaign ${i + 1}`);

  if (data.length === 0) {
    return (
      <div className="text-center text-gray-500 py-12">
        No business metrics data available.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <BaselineWarning baselines={config} />
      <SummaryCards data={data} />
      <CostComparisonChart data={data} names={names} />
      <div className="border-t border-gray-100 pt-6">
        <CumulativeSavingsChart data={data} names={names} />
      </div>
    </div>
  );
}
