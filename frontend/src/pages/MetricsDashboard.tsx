import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  BarChart3,
  Download,
  Loader2,
  AlertCircle,
  Calendar,
  ChevronDown,
} from "lucide-react";

import TechnicalMetricsChart from "../components/charts/TechnicalMetricsChart";
import type { TechnicalEntry } from "../components/charts/TechnicalMetricsChart";
import BusinessMetricsChart from "../components/charts/BusinessMetricsChart";
import CampaignComparisonChart from "../components/charts/CampaignComparisonChart";
import {
  deriveTechnicalMetrics,
  deriveBusinessMetrics,
  exportMetricsCsv,
  exportAggregateMetricsCsv,
  fetchCampaignMetrics,
  fetchAggregateMetrics,
  DEFAULT_BASELINES,
} from "../api/metrics";
import { campaignApi } from "../api/campaigns";
import type {
  BusinessMetrics,
  Campaign,
  CampaignMetrics,
} from "../api/types";

// ---------------------------------------------------------------------------
// Tab definition
// ---------------------------------------------------------------------------

type Tab = "technical" | "business" | "comparison";

const TABS: { key: Tab; label: string }[] = [
  { key: "technical", label: "Technical" },
  { key: "business", label: "Business" },
  { key: "comparison", label: "Comparison" },
];

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export default function MetricsDashboard() {
  const [tab, setTab] = useState<Tab>("technical");
  const [selectedCampaignId, setSelectedCampaignId] = useState<string | "all">(
    "all",
  );
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [exporting, setExporting] = useState(false);

  // -------------------------------------------------------------------------
  // Data fetching
  // -------------------------------------------------------------------------

  const campaignsQuery = useQuery({
    queryKey: ["campaigns"],
    queryFn: () => campaignApi.list({ limit: 100 }),
  });

  const campaigns: Campaign[] = campaignsQuery.data?.data ?? [];

  const aggregateQuery = useQuery({
    queryKey: ["aggregateMetrics", dateFrom, dateTo],
    queryFn: () =>
      fetchAggregateMetrics({
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
      }),
  });

  // Fetch metrics for all completed campaigns (or single selected)
  const campaignIds = useMemo(() => {
    if (selectedCampaignId !== "all") return [selectedCampaignId];
    return campaigns
      .filter((c) => c.status === "completed")
      .map((c) => c.id)
      .slice(0, 20); // cap at 20 for performance
  }, [selectedCampaignId, campaigns]);

  const campaignMetricsQueries = useQuery({
    queryKey: ["campaignMetricsBatch", campaignIds],
    queryFn: async () => {
      const results = await Promise.allSettled(
        campaignIds.map((id) => fetchCampaignMetrics(id)),
      );
      return results
        .map((r, i) => ({
          campaignId: campaignIds[i],
          metrics: r.status === "fulfilled" ? r.value : null,
        }))
        .filter(
          (r): r is { campaignId: string; metrics: CampaignMetrics } =>
            r.metrics !== null,
        );
    },
    enabled: campaignIds.length > 0,
  });

  // -------------------------------------------------------------------------
  // Derived data
  // -------------------------------------------------------------------------

  const campaignMetricsList = campaignMetricsQueries.data ?? [];

  const techEntries: TechnicalEntry[] = useMemo(() => {
    return campaignMetricsList.map((cm) => {
      const campaign = campaigns.find((c) => c.id === cm.campaignId);
      const name = campaign?.campaign_name ?? cm.campaignId.slice(0, 8);
      return {
        campaignName: name,
        metrics: deriveTechnicalMetrics(cm.metrics),
      };
    });
  }, [campaignMetricsList, campaigns]);

  const bizData: { metrics: BusinessMetrics[]; names: string[] } = useMemo(() => {
    const metrics: BusinessMetrics[] = [];
    const names: string[] = [];
    campaignMetricsList.forEach((cm) => {
      const campaign = campaigns.find((c) => c.id === cm.campaignId);
      names.push(campaign?.campaign_name ?? cm.campaignId.slice(0, 8));
      metrics.push(deriveBusinessMetrics(cm.metrics));
    });
    return { metrics, names };
  }, [campaignMetricsList, campaigns]);

  const comparisonEntries = useMemo(() => {
    return campaignMetricsList.map((cm) => {
      const campaign = campaigns.find((c) => c.id === cm.campaignId);
      return {
        label: campaign?.campaign_name ?? cm.campaignId.slice(0, 8),
        metrics: deriveTechnicalMetrics(cm.metrics),
      };
    });
  }, [campaignMetricsList, campaigns]);

  // -------------------------------------------------------------------------
  // Loading / error states
  // -------------------------------------------------------------------------

  const isLoading =
    campaignsQuery.isLoading ||
    aggregateQuery.isLoading ||
    campaignMetricsQueries.isLoading;

  const hasError =
    campaignsQuery.isError ||
    aggregateQuery.isError ||
    campaignMetricsQueries.isError;

  // -------------------------------------------------------------------------
  // Export handler
  // -------------------------------------------------------------------------

  async function handleExport() {
    setExporting(true);
    try {
      if (selectedCampaignId !== "all") {
        await exportMetricsCsv(selectedCampaignId);
      } else {
        await exportAggregateMetricsCsv();
      }
    } catch (err) {
      console.error("Export failed:", err);
    } finally {
      setExporting(false);
    }
  }

  // -------------------------------------------------------------------------
  // Aggregate KPI Summary
  // -------------------------------------------------------------------------

  const aggregate = aggregateQuery.data;

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-blue-50">
            <BarChart3 className="h-6 w-6 text-blue-600" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-gray-900">
              Metrics Dashboard
            </h2>
            <p className="text-sm text-gray-500">
              Performance analytics and business impact
            </p>
          </div>
        </div>
        <button
          onClick={handleExport}
          disabled={exporting || isLoading}
          className="inline-flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 disabled:opacity-50"
        >
          {exporting ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Download className="h-4 w-4" />
          )}
          Export CSV
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        {/* Campaign selector */}
        <div className="relative">
          <select
            value={selectedCampaignId}
            onChange={(e) => setSelectedCampaignId(e.target.value)}
            className="appearance-none w-full sm:w-64 rounded-lg border border-gray-300 bg-white py-2 pl-3 pr-10 text-sm text-gray-700 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="all">All Campaigns</option>
            {campaigns.map((c) => (
              <option key={c.id} value={c.id}>
                {c.campaign_name}
              </option>
            ))}
          </select>
          <ChevronDown className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
        </div>

        {/* Date range */}
        <div className="flex items-center gap-2">
          <Calendar className="h-4 w-4 text-gray-400" />
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            placeholder="From"
          />
          <span className="text-gray-400 text-sm">to</span>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            placeholder="To"
          />
        </div>
      </div>

      {/* Aggregate KPI row */}
      {aggregate && (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4">
          {[
            {
              label: "Total Campaigns",
              value: aggregate.total_campaigns,
            },
            {
              label: "Total Assets",
              value: aggregate.total_assets,
            },
            {
              label: "Avg Processing",
              value: `${aggregate.avg_processing_time_seconds.toFixed(1)}s`,
            },
            {
              label: "Total API Calls",
              value: aggregate.total_api_calls,
            },
            {
              label: "Avg Compliance",
              value: `${aggregate.avg_compliance_pass_rate.toFixed(1)}%`,
            },
          ].map(({ label, value }) => (
            <div
              key={label}
              className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm"
            >
              <p className="text-xs text-gray-500 uppercase tracking-wide">
                {label}
              </p>
              <p className="text-xl font-bold text-gray-900 mt-1">{value}</p>
            </div>
          ))}
        </div>
      )}

      {/* Tab bar */}
      <div className="flex gap-1 rounded-lg bg-gray-100 p-1 w-fit">
        {TABS.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              tab === key
                ? "bg-white text-gray-900 shadow-sm"
                : "text-gray-600 hover:text-gray-900"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Error state */}
      {hasError && (
        <div className="flex items-center gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3">
          <AlertCircle className="h-5 w-5 text-red-500" />
          <p className="text-sm text-red-700">
            Failed to load some metrics data. Some charts may be incomplete.
          </p>
        </div>
      )}

      {/* Loading state */}
      {isLoading && (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
          <span className="ml-3 text-gray-500">Loading metrics...</span>
        </div>
      )}

      {/* Chart panels */}
      {!isLoading && (
        <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
          {tab === "technical" && (
            <TechnicalMetricsChart data={techEntries} />
          )}
          {tab === "business" && (
            <BusinessMetricsChart
              data={bizData.metrics}
              campaignNames={bizData.names}
              baselines={DEFAULT_BASELINES}
            />
          )}
          {tab === "comparison" && (
            <CampaignComparisonChart data={comparisonEntries} />
          )}
        </div>
      )}
    </div>
  );
}
