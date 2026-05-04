import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { TechnicalMetrics } from "../../api/types";

interface CampaignTechEntry {
  label: string;
  metrics: TechnicalMetrics;
}

interface Props {
  data: CampaignTechEntry[];
}

const LOCALE_COLORS = [
  "#3b82f6",
  "#10b981",
  "#f59e0b",
  "#ef4444",
  "#8b5cf6",
  "#ec4899",
  "#14b8a6",
  "#f97316",
];

const RADAR_COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6"];

// ---------------------------------------------------------------------------
// Stacked Bar: Assets by Locale per Campaign
// ---------------------------------------------------------------------------

function AssetsByLocaleChart({ data }: Props) {
  // TechnicalMetrics doesn't carry per-locale breakdowns, so this chart
  // only renders when the caller enriches entries with locale data via the
  // `total_locales_processed` count.  We show a per-campaign bar of total
  // assets instead.
  const chartData = data.map((d) => ({
    name:
      d.label.length > 20 ? d.label.slice(0, 18) + "..." : d.label,
    "Total Assets": d.metrics.total_assets_generated,
    Locales: d.metrics.total_locales_processed,
  }));

  return (
    <div>
      <h3 className="text-sm font-semibold text-gray-700 mb-3">
        Assets Generated per Campaign
      </h3>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart
          data={chartData}
          margin={{ top: 5, right: 20, left: 0, bottom: 5 }}
        >
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
          <Bar
            dataKey="Total Assets"
            fill={LOCALE_COLORS[0]}
            radius={[4, 4, 0, 0]}
          />
          <Bar
            dataKey="Locales"
            fill={LOCALE_COLORS[1]}
            radius={[4, 4, 0, 0]}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Radar Chart: Quality Scores
// ---------------------------------------------------------------------------

function QualityRadarChart({ data }: Props) {
  const dimensions = [
    { key: "api_success_rate", label: "Success Rate" },
    { key: "average_image_quality_score", label: "Image Quality" },
    { key: "api_failure_rate", label: "Failure Rate (inv)", invert: true },
  ];

  const radarData = dimensions.map((dim) => {
    const entry: Record<string, string | number> = { dimension: dim.label };
    data.forEach((d) => {
      const shortName =
        d.label.length > 12 ? d.label.slice(0, 10) + "..." : d.label;
      const raw = d.metrics[dim.key as keyof TechnicalMetrics] as number;
      entry[shortName] = dim.invert ? Math.max(0, 100 - (raw ?? 0)) : (raw ?? 0);
    });
    return entry;
  });

  const campaignNames = data.map((d) =>
    d.label.length > 12 ? d.label.slice(0, 10) + "..." : d.label,
  );

  return (
    <div>
      <h3 className="text-sm font-semibold text-gray-700 mb-3">
        Quality Score Comparison
      </h3>
      {data.length === 0 ? (
        <p className="text-sm text-gray-400 py-8 text-center">
          No quality data available.
        </p>
      ) : (
        <ResponsiveContainer width="100%" height={350}>
          <RadarChart cx="50%" cy="50%" outerRadius="70%" data={radarData}>
            <PolarGrid stroke="#e5e7eb" />
            <PolarAngleAxis
              dataKey="dimension"
              tick={{ fontSize: 11, fill: "#6b7280" }}
            />
            <PolarRadiusAxis
              angle={90}
              domain={[0, 100]}
              tick={{ fontSize: 10 }}
            />
            <Tooltip
              contentStyle={{
                borderRadius: "8px",
                border: "1px solid #e5e7eb",
                fontSize: "13px",
              }}
            />
            <Legend wrapperStyle={{ fontSize: "13px" }} />
            {campaignNames.map((name, idx) => (
              <Radar
                key={name}
                name={name}
                dataKey={name}
                stroke={RADAR_COLORS[idx % RADAR_COLORS.length]}
                fill={RADAR_COLORS[idx % RADAR_COLORS.length]}
                fillOpacity={0.15}
                strokeWidth={2}
              />
            ))}
          </RadarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Side-by-Side Comparison Table
// ---------------------------------------------------------------------------

function ComparisonTable({ data }: Props) {
  return (
    <div className="overflow-x-auto">
      <h3 className="text-sm font-semibold text-gray-700 mb-3">
        Campaign Comparison
      </h3>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200 text-left">
            <th className="py-2 pr-4 font-medium text-gray-600">Campaign</th>
            <th className="py-2 px-3 font-medium text-gray-600 text-right">Assets</th>
            <th className="py-2 px-3 font-medium text-gray-600 text-right">
              Gen Time (s)
            </th>
            <th className="py-2 px-3 font-medium text-gray-600 text-right">
              Success %
            </th>
            <th className="py-2 px-3 font-medium text-gray-600 text-right">
              Tokens
            </th>
          </tr>
        </thead>
        <tbody>
          {data.map((d) => (
            <tr key={d.label} className="border-b border-gray-100">
              <td className="py-2 pr-4 font-medium text-gray-900">
                {d.label}
              </td>
              <td className="py-2 px-3 text-right text-gray-700">
                {d.metrics.total_assets_generated}
              </td>
              <td className="py-2 px-3 text-right text-gray-700">
                {d.metrics.total_generation_time.toFixed(1)}
              </td>
              <td className="py-2 px-3 text-right">
                <span
                  className={
                    d.metrics.api_success_rate >= 90
                      ? "text-green-600 font-medium"
                      : d.metrics.api_success_rate >= 70
                        ? "text-amber-600 font-medium"
                        : "text-red-600 font-medium"
                  }
                >
                  {d.metrics.api_success_rate.toFixed(1)}%
                </span>
              </td>
              <td className="py-2 px-3 text-right text-gray-600">
                {d.metrics.total_tokens_used.toLocaleString()}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Combined Comparison Panel
// ---------------------------------------------------------------------------

export default function CampaignComparisonChart({ data }: Props) {
  if (data.length === 0) {
    return (
      <div className="text-center text-gray-500 py-12">
        No campaign data available for comparison.
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <ComparisonTable data={data} />
      <div className="border-t border-gray-100 pt-6">
        <AssetsByLocaleChart data={data} />
      </div>
      <div className="border-t border-gray-100 pt-6">
        <QualityRadarChart data={data} />
      </div>
    </div>
  );
}
