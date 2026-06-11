// ---------------------------------------------------------------------------
// Auth Types
//
// Token model (P5-T3): COOKIE-BASED. The backend sets the access AND refresh
// tokens as httpOnly cookies; the browser never reads either. The frontend does
// NOT store tokens (no localStorage) and does NOT send an Authorization header —
// it relies on `credentials: "include"` so the cookies ride along.
//
// `TokenResponse` below is the login/refresh response BODY shape. The browser
// ignores the token fields (they exist for non-browser API clients); only the
// Set-Cookie headers matter for the SPA. The server also returns a
// `refresh_token` field in the body, but a cookie client never uses it.
// ---------------------------------------------------------------------------

/** Server enum: UserRole. */
export type UserRole = "viewer" | "editor" | "admin";

export interface User {
  id: string;
  email: string;
  display_name: string;
  role: "admin" | "editor" | "viewer";
  created_at: string;
}

/**
 * Login/refresh response body. The SPA ignores these token fields (auth is
 * carried by httpOnly cookies); they are present for non-browser API clients.
 */
export interface TokenResponse {
  access_token: string;
  refresh_token: string;
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

/**
 * Server enum: CampaignStatus. The server only emits these four values; the
 * `status` field on response models is typed as a plain string on the wire, so
 * `Campaign`/`CampaignListItem` keep `status: string` for forward-compat.
 */
export type CampaignStatus = "draft" | "processing" | "completed" | "failed";

/** Full campaign representation (server: CampaignResponse). */
export interface Campaign {
  id: string;
  campaign_id: string;
  campaign_name: string;
  brand_name: string;
  status: string;
  image_backend: string;
  brand_guidelines_id: string | null;
  brief: Record<string, unknown>;
  target_locales: string[];
  aspect_ratios: string[];
  created_by: string | null;
  created_at: string;
  updated_at: string;
  asset_count: number;
  latest_job?: Job | null;
}

/** Slim campaign representation in list responses (server: CampaignListItem). */
export interface CampaignListItem {
  id: string;
  campaign_id: string;
  campaign_name: string;
  brand_name: string;
  status: string;
  image_backend: string;
  asset_count: number;
  created_at: string;
  updated_at: string;
}

/** Payload to create a campaign (server: CampaignCreateRequest). */
export interface CampaignCreate {
  campaign_id: string;
  campaign_name: string;
  brand_name: string;
  brand_guidelines_id?: string | null;
  image_backend?: string;
  brief?: Record<string, unknown>;
  target_locales?: string[];
  aspect_ratios?: string[];
}

/** Partial-update payload (server: CampaignUpdateRequest, draft only). */
export interface CampaignUpdate {
  campaign_name?: string | null;
  brief?: Record<string, unknown> | null;
  target_locales?: string[] | null;
  aspect_ratios?: string[] | null;
  image_backend?: string | null;
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

/** Async generation job (server: JobResponse). `status` is a plain string on
 * the wire, backed by the JobStatus enum. */
export interface Job {
  id: string;
  campaign_id: string;
  status: string;
  progress_percent: number;
  current_stage: string | null;
  result: Record<string, unknown> | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Brand Guidelines Types
// ---------------------------------------------------------------------------

/** Server: BrandResponse. */
export interface BrandGuideline {
  id: string;
  name: string;
  source_file_path?: string | null;
  primary_colors?: string[] | null;
  secondary_colors?: string[] | null;
  primary_font?: string | null;
  secondary_font?: string | null;
  brand_voice?: string | null;
  photography_style?: string | null;
  raw_extracted_data?: Record<string, unknown> | null;
  created_by?: string | null;
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

/**
 * @deprecated Server returns violations as free-form objects (see
 * ComplianceReportResponse.violations). Kept for any callers referencing the
 * old structured shape.
 */
export interface ComplianceViolation {
  severity: "error" | "warning" | "info";
  rule: string;
  message: string;
  field?: string;
}

/** Server: ComplianceReportResponse. */
export interface ComplianceReport {
  id: string;
  campaign_id: string;
  is_compliant: boolean | null;
  violations: Record<string, unknown>[];
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

/** Server: PaginationMeta — page-based, not cursor-based. */
export interface PaginationMeta extends Meta {
  page: number;
  per_page: number;
  total: number;
  total_pages: number;
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
