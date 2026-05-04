import { api } from "./client";
import type {
  AggregateMetrics,
  BusinessMetrics,
  BusinessMetricsConfig,
  CampaignMetrics,
  DateRangeParams,
  Envelope,
  TechnicalMetrics,
} from "./types";

// ---------------------------------------------------------------------------
// Default business baselines (configurable in UI)
// ---------------------------------------------------------------------------

export const DEFAULT_BASELINES: BusinessMetricsConfig = {
  manual_baseline_hours: 0.75, // hours per asset manually
  manual_baseline_cost: 150, // USD per asset manually
  manual_baseline_assets: 8, // assets a designer produces per day
  hourly_rate: 75, // designer hourly rate
};

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

export async function fetchCampaignMetrics(
  campaignId: string,
): Promise<CampaignMetrics> {
  const res = await api.get<Envelope<CampaignMetrics>>(
    `/campaigns/${campaignId}/metrics`,
  );
  return res.data;
}

export async function fetchAggregateMetrics(
  params?: DateRangeParams,
): Promise<AggregateMetrics> {
  const query = new URLSearchParams();
  if (params?.date_from) query.set("date_from", params.date_from);
  if (params?.date_to) query.set("date_to", params.date_to);
  const qs = query.toString();
  const res = await api.get<Envelope<AggregateMetrics>>(
    `/metrics/aggregate${qs ? `?${qs}` : ""}`,
  );
  return res.data;
}

// ---------------------------------------------------------------------------
// CSV export (triggers browser download)
// ---------------------------------------------------------------------------

/**
 * Export campaign metrics as CSV.
 *
 * First attempts a server-side export endpoint. If that returns 404 (endpoint
 * not yet deployed), falls back to a client-side CSV built from the JSON
 * metrics response.
 */
export async function exportMetricsCsv(campaignId: string): Promise<void> {
  try {
    const res = await api.getRaw(
      `/campaigns/${campaignId}/metrics/export`,
    );
    const blob = await res.blob();
    const disposition = res.headers.get("Content-Disposition") ?? "";
    const match = disposition.match(/filename="?([^";\n]+)"?/);
    const filename = match
      ? match[1]
      : `campaign_${campaignId}_metrics.csv`;
    triggerDownload(blob, filename);
    return;
  } catch {
    // Fall through to client-side generation.
  }

  // Client-side fallback: build CSV from JSON metrics.
  const metrics = await fetchCampaignMetrics(campaignId);
  const tech = deriveTechnicalMetrics(metrics);
  const biz = deriveBusinessMetrics(metrics);

  const rows = [
    ["Metric", "Value"],
    ["Total Generation Time (s)", String(tech.total_generation_time)],
    ["Average Generation Time (s)", String(tech.average_generation_time)],
    ["Total API Calls", String(tech.total_api_calls)],
    ["API Success Rate (%)", String(tech.api_success_rate)],
    ["API Failure Rate (%)", String(tech.api_failure_rate)],
    ["Products Processed", String(tech.total_products_processed)],
    ["Locales Processed", String(tech.total_locales_processed)],
    ["Assets Generated", String(tech.total_assets_generated)],
    ["Avg File Size (KB)", String(tech.average_file_size_kb)],
    ["Total File Size (MB)", String(tech.total_file_size_mb)],
    ["Avg Image Quality Score", String(tech.average_image_quality_score)],
    ["Prompt Tokens Used", String(tech.prompt_tokens_used)],
    ["Completion Tokens Used", String(tech.completion_tokens_used)],
    ["Total Tokens Used", String(tech.total_tokens_used)],
    ["Peak Memory Usage (MB)", String(tech.peak_memory_usage_mb)],
    ["", ""],
    ["Estimated Manual Hours", String(biz.estimated_manual_hours)],
    ["Estimated Manual Cost ($)", String(biz.estimated_manual_cost)],
    ["Actual Generation Cost ($)", String(biz.actual_generation_cost)],
    ["Cost Savings ($)", String(biz.cost_savings)],
    ["Cost Savings (%)", String(biz.cost_savings_percent)],
    ["Time Savings (h)", String(biz.time_savings_hours)],
    ["ROI (%)", String(biz.roi_percent)],
    ["Cost Per Asset ($)", String(biz.cost_per_asset)],
    ["Assets Per Hour", String(biz.assets_per_hour)],
    ["Quality Consistency Score", String(biz.quality_consistency_score)],
    ["Brand Compliance Rate (%)", String(biz.brand_compliance_rate)],
    ["Localization Coverage (%)", String(biz.localization_coverage_percent)],
    ["Revision Rate (%)", String(biz.revision_rate)],
  ];

  const csvContent = rows.map((r) => r.join(",")).join("\n");
  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  triggerDownload(
    blob,
    `metrics_${campaignId}_${new Date().toISOString().slice(0, 10)}.csv`,
  );
}

export async function exportAggregateMetricsCsv(): Promise<void> {
  const metrics = await fetchAggregateMetrics();

  const rows = [
    ["Metric", "Value"],
    ["Total Campaigns", String(metrics.total_campaigns)],
    ["Total Assets", String(metrics.total_assets)],
    ["Avg Processing Time (s)", String(metrics.avg_processing_time_seconds)],
    ["Total API Calls", String(metrics.total_api_calls)],
    ["Avg Compliance Pass Rate (%)", String(metrics.avg_compliance_pass_rate)],
    ...Object.entries(metrics.campaigns_by_status).map(([k, v]) => [
      `Campaigns - ${k}`,
      String(v),
    ]),
    ...Object.entries(metrics.campaigns_by_backend).map(([k, v]) => [
      `Backend - ${k}`,
      String(v),
    ]),
  ];

  const csvContent = rows.map((r) => r.join(",")).join("\n");
  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  triggerDownload(
    blob,
    `aggregate_metrics_${new Date().toISOString().slice(0, 10)}.csv`,
  );
}

// ---------------------------------------------------------------------------
// Derived metrics helpers
// ---------------------------------------------------------------------------

/**
 * Derive the 17-field TechnicalMetrics from a CampaignMetrics response.
 * Fields that cannot be inferred from the server payload default to zero.
 */
export function deriveTechnicalMetrics(
  raw: CampaignMetrics,
): TechnicalMetrics {
  const totalAssets = raw.total_assets || 1;
  const avgGenTime =
    totalAssets > 0 ? raw.processing_time_seconds / totalAssets : 0;
  const totalLocales = Object.keys(raw.assets_by_locale).length;

  return {
    total_generation_time: raw.processing_time_seconds,
    average_generation_time: round(avgGenTime),
    total_api_calls: raw.api_calls,
    api_success_rate: raw.compliance_pass_rate,
    api_failure_rate: round(100 - raw.compliance_pass_rate),
    total_products_processed: 0, // not available from summary endpoint
    total_locales_processed: totalLocales,
    total_assets_generated: raw.total_assets,
    average_file_size_kb: 0,
    total_file_size_mb: 0,
    average_image_quality_score: 0,
    prompt_tokens_used: 0,
    completion_tokens_used: 0,
    total_tokens_used: 0,
    processing_start_time: "",
    processing_end_time: "",
    peak_memory_usage_mb: 0,
  };
}

/**
 * Derive the 13-field BusinessMetrics from a CampaignMetrics response
 * using the supplied baselines.
 */
export function deriveBusinessMetrics(
  raw: CampaignMetrics,
  baselines: BusinessMetricsConfig = DEFAULT_BASELINES,
): BusinessMetrics {
  const totalAssets = raw.total_assets;
  const manualHours = totalAssets * baselines.manual_baseline_hours;
  const manualCost = totalAssets * baselines.manual_baseline_cost;
  const actualCost = raw.cost_estimate_usd;
  const automatedHours = raw.processing_time_seconds / 3600;
  const costSavings = manualCost - actualCost;
  const timeSavings = manualHours - automatedHours;

  return {
    estimated_manual_hours: round(manualHours),
    estimated_manual_cost: round(manualCost),
    actual_generation_cost: round(actualCost),
    cost_savings: round(costSavings),
    cost_savings_percent: manualCost > 0
      ? round((costSavings / manualCost) * 100)
      : 0,
    time_savings_hours: round(timeSavings),
    roi_percent: actualCost > 0
      ? round((costSavings / actualCost) * 100)
      : 0,
    cost_per_asset: totalAssets > 0
      ? round(actualCost / totalAssets)
      : 0,
    assets_per_hour: automatedHours > 0
      ? round(totalAssets / automatedHours)
      : 0,
    quality_consistency_score: 0, // requires per-asset quality data
    brand_compliance_rate: raw.compliance_pass_rate,
    localization_coverage_percent: 0, // requires target vs actual locale comparison
    revision_rate: 0,
  };
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

function round(value: number, decimals: number = 2): number {
  const factor = 10 ** decimals;
  return Math.round(value * factor) / factor;
}

function triggerDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

// ---------------------------------------------------------------------------
// Convenience export matching the pattern in other API modules
// ---------------------------------------------------------------------------

export const metricsApi = {
  campaign: fetchCampaignMetrics,
  aggregate: fetchAggregateMetrics,
  exportCsv: exportMetricsCsv,
  exportAggregateCsv: exportAggregateMetricsCsv,
};
