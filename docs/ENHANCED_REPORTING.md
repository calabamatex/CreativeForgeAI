# Campaign Reporting

The pipeline writes a JSON report per product per campaign run, capturing technical metrics measured during execution.

## Report location and filename

```
output/campaign_reports/campaign_report_{CAMPAIGN_ID}_{PRODUCT_ID}_{YYYY-MM-DD}.json
```

Reports are timestamped and never overwritten — re-running the same campaign on the same day will overwrite that day's file, but reports from prior days persist.

## What's measured

The `TechnicalMetrics` record (17 fields) is populated from real instrumentation during the pipeline run:

| Field | What it captures | How it's measured |
|---|---|---|
| `backend_used` | Active image-generation backend | Resolved from CLI flag, brief, or env |
| `total_api_calls` | Image-generation API calls made | Counter incremented at each call |
| `cache_hits` / `cache_misses` | Hero-image reuse vs. regeneration | Counter at the cache decision point |
| `cache_hit_rate` | `hits / (hits + misses) * 100` | Computed at end of run |
| `retry_count` / `retry_reasons` | Retried API calls and why | Reserved fields; current implementation does not increment these in the retry handlers |
| `avg/min/max_api_response_time_ms` | Wall-clock per image-gen call | `time.time()` deltas around `await self.image_service.generate_image(...)` |
| `image_processing_time_ms` | Total resize + overlay + post-process time | Summed `time.time()` deltas around image-processor calls |
| `localization_time_ms` | Total Claude localization time | Summed deltas around `claude_service.localize_message(...)` |
| `compliance_check_time_ms` | Time spent in legal-compliance linter | Delta around `LegalComplianceChecker.check_content(...)` |
| `peak_memory_mb` | Process peak resident memory | `psutil.Process().memory_info().rss`, sampled per product |
| `system_info` | Platform, Python version, processor | `platform` module |
| `full_error_traces` | Stack traces for any caught product-level exceptions | `traceback.format_exc()` on exception |

## What's not reported (and why)

Earlier versions of this pipeline reported a `BusinessMetrics` block with fields like `roi_multiplier`, `cost_savings_percentage`, `time_saved_vs_manual_hours`, and `estimated_savings`. These were removed because the calculations were tautologies, not measurements:

- `manual_baseline_hours = 96.0` — hard-coded constant, no source
- `manual_baseline_cost = 2700.0` — hard-coded constant, no source
- `cost_savings_percentage = 80.0 + (cache_hit_rate * 0.15)` — assumption returned as output
- `roi_multiplier = estimated_savings / actual_cost_estimate` — algebraically `0.80 / 0.20 = 4.0` by construction

A field that is determined entirely by hard-coded inputs is not a metric; it's a restatement of the input. To produce honest business metrics here, the following inputs would need to be wired in:

1. **Real per-call API cost** — pulled from each provider's billing API (or a configurable per-backend rate card).
2. **A measured manual-production baseline** — observed time and cost from a real comparable manual workflow at the user's organization.
3. **A defined cost-of-time input** — fully-loaded hourly rate for the relevant role (creative producer, designer, etc.), supplied per deployment.

With those three inputs the pipeline could honestly compute cost-per-asset, time-per-asset, and a delta vs. the user's own manual baseline. Without them, any "ROI" number reported is fiction.

## Reading a report

A typical report after a successful Gemini run looks like:

```json
{
  "campaign_id": "PREMIUM2026",
  "campaign_name": "Premium Tech Launch",
  "generated_assets": [
    {
      "product_id": "EARBUDS-001",
      "locale": "en-US",
      "aspect_ratio": "1:1",
      "file_path": "output/EARBUDS-001/PREMIUM2026/en-US/1_1/EARBUDS-001_1_1_en-US.png",
      "generation_method": "gemini",
      "timestamp": "2026-04-19T17:42:11.331Z"
    }
  ],
  "total_assets": 6,
  "processing_time_seconds": 41.2,
  "success_rate": 1.0,
  "errors": [],
  "technical_metrics": {
    "backend_used": "gemini",
    "total_api_calls": 1,
    "cache_hits": 0,
    "cache_misses": 1,
    "cache_hit_rate": 0.0,
    "avg_api_response_time_ms": 1810.4,
    "min_api_response_time_ms": 1810.4,
    "max_api_response_time_ms": 1810.4,
    "image_processing_time_ms": 2104.6,
    "localization_time_ms": 0.0,
    "compliance_check_time_ms": 0.0,
    "peak_memory_mb": 168.3,
    "system_info": {
      "platform": "Darwin",
      "python_version": "3.11.5",
      "processor": "arm64"
    },
    "full_error_traces": []
  }
}
```

## Console output

At the end of a run the pipeline prints a summary block:

```
✅ Campaign processing complete!
   Total assets generated: 6
   Processing time: 41.2 seconds
   Success rate: 100.0%
   Reports saved: 1 product reports

📊 Technical Metrics:
   Backend: gemini
   API Calls: 1 total, 0 cache hits (0.0% hit rate)
   API Response Time: 1810ms avg (1810-1810ms range)
   Image Processing: 2105ms total
   Localization: 0ms total
   Peak Memory: 168.3 MB
```

## Performance overhead

Metric collection adds approximately 20-30 ms per campaign (mostly `psutil` memory polling and the report write). This is dominated by API and image-processing time and is not a meaningful contributor to total runtime.
