// ---------------------------------------------------------------------------
// Auth Types
// ---------------------------------------------------------------------------

export interface User {
  id: string;
  email: string;
  display_name: string;
  role: "admin" | "editor" | "viewer";
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface LoginRequest {
  email: string;
  password: string;
}

// ---------------------------------------------------------------------------
// Campaign Types
// ---------------------------------------------------------------------------

export type CampaignStatus =
  | "draft"
  | "queued"
  | "processing"
  | "completed"
  | "failed"
  | "cancelled";

export interface Campaign {
  id: string;
  campaign_id: string;
  campaign_name: string;
  brand_name: string;
  status: CampaignStatus;
  brief: Record<string, unknown>;
  image_backend: string;
  target_locales: string[];
  aspect_ratios: string[];
  created_at: string;
  updated_at: string;
  asset_count: number;
  job?: Job;
}

export interface CampaignCreate {
  brief: Record<string, unknown>;
  brand_guidelines_id?: string;
  image_backend?: string;
}

export interface CampaignUpdate {
  campaign_name?: string;
  brand_name?: string;
  status?: CampaignStatus;
  brief?: Record<string, unknown>;
  image_backend?: string;
  target_locales?: string[];
  aspect_ratios?: string[];
}

// ---------------------------------------------------------------------------
// Asset Types
// ---------------------------------------------------------------------------

export interface Asset {
  id: string;
  campaign_id: string;
  product_id: string;
  locale: string;
  aspect_ratio: string;
  file_path: string;
  storage_key: string;
  file_size_bytes: number | null;
  width: number | null;
  height: number | null;
  generation_method: string;
  generation_time_ms: number | null;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Job Types
// ---------------------------------------------------------------------------

export type JobStatus =
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export interface Job {
  id: string;
  campaign_id: string;
  status: JobStatus;
  progress_percent: number;
  current_stage: string | null;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
}

// ---------------------------------------------------------------------------
// Brand Guidelines Types
// ---------------------------------------------------------------------------

export interface BrandGuideline {
  id: string;
  name: string;
  primary_colors: string[];
  secondary_colors: string[];
  primary_font: string;
  secondary_font: string | null;
  brand_voice: string | null;
  photography_style: string | null;
  created_at: string;
  updated_at: string;
}

/** @deprecated Use BrandGuideline instead. Kept for backward compatibility. */
export type BrandGuidelines = BrandGuideline;

export interface BrandGuidelineCreate {
  name: string;
  primary_colors?: string[];
  secondary_colors?: string[];
  primary_font?: string;
  secondary_font?: string;
  brand_voice?: string;
  photography_style?: string;
}

// ---------------------------------------------------------------------------
// Compliance Types
// ---------------------------------------------------------------------------

export interface ComplianceViolation {
  severity: "error" | "warning" | "info";
  rule: string;
  message: string;
  field?: string;
}

export interface ComplianceReport {
  id: string;
  campaign_id: string;
  is_compliant: boolean;
  violations: ComplianceViolation[];
  summary: Record<string, unknown>;
  checked_at: string;
}

// ---------------------------------------------------------------------------
// Metrics Types
// ---------------------------------------------------------------------------

/** Server-side campaign metrics matching CampaignMetricsResponse schema. */
export interface CampaignMetrics {
  campaign_id: string;
  total_assets: number;
  assets_by_locale: Record<string, number>;
  assets_by_ratio: Record<string, number>;
  processing_time_seconds: number;
  api_calls: number;
  cache_hit_rate: number;
  compliance_pass_rate: number;
  cost_estimate_usd: number;
}

/** Server-side aggregate metrics matching AggregateMetricsResponse schema. */
export interface AggregateMetrics {
  total_campaigns: number;
  total_assets: number;
  avg_processing_time_seconds: number;
  total_api_calls: number;
  avg_compliance_pass_rate: number;
  campaigns_by_status: Record<string, number>;
  campaigns_by_backend: Record<string, number>;
}

/** Detailed technical metrics for a generation run (17 fields). */
export interface TechnicalMetrics {
  total_generation_time: number;
  average_generation_time: number;
  total_api_calls: number;
  api_success_rate: number;
  api_failure_rate: number;
  total_products_processed: number;
  total_locales_processed: number;
  total_assets_generated: number;
  average_file_size_kb: number;
  total_file_size_mb: number;
  average_image_quality_score: number;
  prompt_tokens_used: number;
  completion_tokens_used: number;
  total_tokens_used: number;
  processing_start_time: string;
  processing_end_time: string;
  peak_memory_usage_mb: number;
}

/** Business/ROI metrics for a generation run (13 fields). */
export interface BusinessMetrics {
  estimated_manual_hours: number;
  estimated_manual_cost: number;
  actual_generation_cost: number;
  cost_savings: number;
  cost_savings_percent: number;
  time_savings_hours: number;
  roi_percent: number;
  cost_per_asset: number;
  assets_per_hour: number;
  quality_consistency_score: number;
  brand_compliance_rate: number;
  localization_coverage_percent: number;
  revision_rate: number;
}

/** Configuration baselines used to compute BusinessMetrics. */
export interface BusinessMetricsConfig {
  manual_baseline_hours: number;
  manual_baseline_cost: number;
  manual_baseline_assets: number;
  hourly_rate: number;
}

/** Query params for date-range filtered metrics requests. */
export interface DateRangeParams {
  date_from?: string;
  date_to?: string;
}

// ---------------------------------------------------------------------------
// Generic Response Wrappers
// ---------------------------------------------------------------------------

export interface Meta {
  request_id: string;
  timestamp: string;
}

export interface PaginationMeta extends Meta {
  total: number;
  limit: number;
  cursor: string | null;
  has_more: boolean;
}

export interface Envelope<T> {
  data: T;
  meta: Meta;
}

export interface PaginatedEnvelope<T> {
  data: T[];
  meta: PaginationMeta;
}

/**
 * Generic paginated response. Alias kept for callers that prefer this name.
 */
export type PaginatedResponse<T> = PaginatedEnvelope<T>;

/**
 * Generic API response. Alias kept for callers that prefer this name.
 */
export type ApiResponse<T> = Envelope<T>;
