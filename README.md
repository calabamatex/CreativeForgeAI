# GenAI Creative Automation Platform

> **AI-powered creative automation platform for generating localized, brand-compliant marketing assets at scale**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

---

## 🚀 Overview

GenAI Creative Automation Platform is an enterprise-grade system that automates the creation of marketing assets using generative AI. It combines **multiple AI image generation backends** (Adobe Firefly, OpenAI DALL-E, Google Gemini) with **intelligent text localization** (Claude 3.5 Sonnet) and **legal compliance checking** to produce brand-consistent, legally compliant marketing materials across multiple locales and formats.

### Key Capabilities

- 🎨 **Multi-Backend Image Generation** - Adobe Firefly, OpenAI DALL-E 3, Google Gemini Imagen 4
- 🌍 **AI-Powered Localization** - Claude 3.5 Sonnet for culturally-adapted messaging
- ⚖️ **Legal Compliance Checking** - Pre-generation validation (FTC, FDA, SEC, FINRA)
- 🎭 **Brand Guidelines Enforcement** - Automated brand consistency across all assets
- 📐 **Multi-Format Asset Output** - 1:1, 16:9, 9:16, 4:5 aspect ratios. The default generates one square hero, then center-crops to each ratio. Native per-ratio generation (one API call per ratio) is available as an opt-in flag (`native_aspect_ratios`); end-to-end native output remains *in progress* pending live-backend verification.
- 🔄 **Asset Reuse System** - Intelligent caching to reduce API costs
- 🎨 **Advanced Text Customization** - Colors, shadows, backgrounds with brand control
- 🖼️ **Logo Placement** - Automated logo overlay with 4-corner positioning
- 📊 **Campaign Analytics** - Technical metrics measured per run (API timing, cache efficiency, memory)

---

## 📋 Table of Contents

- [Features](#-features)
- [Quick Start](#-quick-start)
- [Installation](#-installation)
- [Usage](#-usage)
- [Architecture](#-architecture)
- [Documentation](#-documentation)
- [Examples](#-examples)
- [Contributing](#-contributing)
- [License](#-license)

---

## ✨ Features

### Image Generation
- ✅ **Adobe Firefly** - Enterprise-grade, commercially-safe generation
- ✅ **OpenAI DALL-E 3** - High-quality, creative generation
- ✅ **Google Gemini Imagen 4** - Latest Google AI image generation
- ✅ **Automatic fallback** - Switch backends seamlessly
- ✅ **Hero image caching** - Generate once, reuse across formats

### Localization & Translation
- ✅ **Claude 3.5 Sonnet** - Context-aware message localization
- ✅ **Cultural adaptation** - Not just translation, but cultural relevance
- ✅ **Multiple locales** - en-US, es-MX, en-GB, fr-FR, de-DE, ja-JP, and more
- ✅ **Tone preservation** - Maintains brand voice across languages
- ✅ **Localization guidelines** - Customizable per-locale rules

### Legal Compliance
- ✅ **Pre-generation validation** - Catch issues before asset creation
- ✅ **Industry templates** - General, Health/FDA, Financial/SEC
- ✅ **Three severity levels** - Error (blocks), Warning (advisory), Info (reminders)
- ✅ **Prohibited content detection** - Words, phrases, claims
- ✅ **Required disclaimers** - Automatic tracking and reminders
- ✅ **Locale-specific rules** - Different regulations per market

### Brand Guidelines
- ✅ **Color palette enforcement** - Primary, secondary, accent colors
- ✅ **Typography control** - Font family, sizes, weights
- ✅ **Text customization** - Colors, shadows, backgrounds, opacity
- ✅ **Logo placement** - 4-corner positioning with sizing control
- ✅ **Design system compliance** - Consistent brand experience

### Asset Management
- 🔶 **Multi-format output** *(in progress)* - Square (1:1), Landscape (16:9), Portrait (9:16), Portrait (4:5). By default a single square hero is generated and center-cropped to the other ratios. Native per-ratio generation is wired as an opt-in (`native_aspect_ratios` on the brief), with per-backend ratio→size maps; it stays *in progress* until verified against a live backend (cost guard: native issues one paid call per ratio). See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
- ✅ **Multiple output formats** - PNG, JPEG, WebP
- ✅ **Asset reuse** - Intelligent caching system
- ✅ **Organized storage** - Campaign/Locale/Product/Format hierarchy
- ✅ **Brief updates** - Automatic tracking of generated assets

### Campaign Analytics & Reporting
- ✅ **Technical metrics** - API response times, cache efficiency, memory usage (measured per run)
- 🔶 **Cost / API-call accounting** *(in progress)* - The API metrics endpoints currently return placeholder zeros for `api_calls`, `cache_hit_rate`, and `cost_estimate_usd`; real wiring is being delivered in a later phase. See [Roadmap](#-roadmap).
- ✅ **Performance tracking** - Processing times, localization efficiency, asset throughput
- ✅ **Compliance monitoring** - Pass rates, violation tracking
- ✅ **Historical reports** - Timestamped reports in `output/campaign_reports/`
- ✅ **Asset inventory** - Complete manifest of generated assets
- ✅ **JSON reports** - Machine-readable campaign summaries with full metrics
- ✅ **Error reporting** - Full stack traces for debugging

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- API Keys:
  - **Anthropic** (Claude) - Required for localization
  - **OpenAI** (optional) - For DALL-E 3 generation
  - **Google AI Studio** (optional) - For Gemini Imagen 4
  - **Adobe Firefly** (optional) - For Adobe Firefly generation

### 1. Clone & Install

```bash
# Clone repository
git clone https://github.com/yourusername/adobe-genai-project.git
cd adobe-genai-project

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies (full app: API + worker + S3 storage)
# Dependencies are defined in pyproject.toml — the single source of truth.
pip install -e ".[api,worker,s3]"

# CLI pipeline only:        pip install -e "."
# Contributors (lint/types/tests): pip install -e ".[api,worker,s3,dev]"
```

### 2. Start Local Dev Services (Postgres + Redis + MinIO)

The API/worker stack uses Postgres, Redis, and MinIO (S3-compatible storage),
provided by Docker Compose. Bring them up and create the assets bucket:

```bash
# Start Postgres, Redis, MinIO (+ a one-shot job that creates the bucket)
docker compose up -d

# Wait until all show "(healthy)"
docker compose ps
```

> **Host ports are remapped** to avoid clashing with other local stacks:
> Postgres `localhost:5434`, Redis `localhost:6380`, MinIO API `localhost:9002`
> (console `localhost:9003`). See `docs/FOUND_ISSUES.md` for the why.

Copy the env template — its local-dev defaults already point at these services
with working credentials (non-secret, local only):

```bash
cp .env.example .env
```

The `minio-init` Compose service creates the `genai-assets` bucket on `up`. To
(re)create it manually:

```bash
docker run --rm --network host minio/mc:latest /bin/sh -c \
  "mc alias set local http://localhost:9002 minioadmin minioadmin && \
   mc mb --ignore-existing local/genai-assets"
```

**Sanity-check connectivity** (with `.env` loaded — `set -a; . ./.env; set +a`):

```bash
# Postgres: apply migrations
alembic upgrade head

# Redis
python -c "import asyncio,redis.asyncio as r; asyncio.run(r.from_url('redis://localhost:6380/0').ping()); print('redis ok')"

# MinIO / S3: list the assets bucket via the repo storage backend
STORAGE_BACKEND=s3 python -c "import asyncio; from src.storage_factory import get_default_storage_backend as g; asyncio.run(g().list_keys('')); print('minio ok')"
```

### 3. Configure API Keys

Add your API keys to the `.env` file in the project root:

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-your-key-here

# Optional (choose at least one image backend)
OPENAI_API_KEY=sk-your-key-here
GOOGLE_API_KEY=your-key-here
ADOBE_CLIENT_ID=your-client-id
ADOBE_CLIENT_SECRET=your-client-secret
```

### 4. Run Your First Campaign

```bash
# Process example campaign
./run_cli.sh examples/campaign_brief.json
```

That's it! Your assets will be generated in `output/[PRODUCT_ID]/[CAMPAIGN_ID]/`

---

## 📚 Documentation

### Core Documentation
- **[QUICKSTART.md](QUICKSTART.md)** - Step-by-step setup guide
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System design and components
- **[FEATURES.md](FEATURES.md)** - Complete feature matrix
- **[API.md](docs/API.md)** - API reference
- **[PACKAGES.md](docs/PACKAGES.md)** - Code package summaries

### Feature Guides
- **[BRAND_GUIDELINES.md](docs/BRAND_GUIDELINES.md)** - Complete brand guidelines system
- **[LOCALIZATION.md](docs/LOCALIZATION.md)** - AI-powered localization guide
- **[TEXT_CUSTOMIZATION.md](docs/TEXT_CUSTOMIZATION.md)** - Text colors, shadows, backgrounds
- **[LOGO_PLACEMENT.md](docs/LOGO_PLACEMENT.md)** - Logo overlay configuration
- **[IMAGE_QUALITY_OPTIMIZATION.md](docs/IMAGE_QUALITY_OPTIMIZATION.md)** - Advanced prompt engineering
- **[ENHANCED_REPORTING.md](docs/ENHANCED_REPORTING.md)** - Technical & business metrics (NEW!)
- **[LEGAL_COMPLIANCE.md](examples/guidelines/LEGAL_COMPLIANCE.md)** - Legal checking system
- **[LEGAL_EXAMPLES.md](examples/guidelines/LEGAL_EXAMPLES.md)** - Compliance examples

### Tools & Scripts
- **[scripts/README.md](scripts/README.md)** - Campaign brief generator and utilities

### Contributing
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - Development guidelines
- **[CHANGELOG.md](CHANGELOG.md)** - Version history

---

## 📁 Project Structure

```
adobe-genai-project/
├── src/
│   ├── genai/              # AI service integrations
│   │   ├── firefly.py      # Adobe Firefly client
│   │   ├── openai_client.py # OpenAI DALL-E client
│   │   ├── gemini.py       # Google Gemini client
│   │   ├── claude.py       # Claude localization service
│   │   └── factory.py      # Image generation factory
│   ├── parsers/            # Guidelines parsers
│   │   ├── brand_parser.py
│   │   ├── localization_parser.py
│   │   └── legal_parser.py
│   ├── models.py           # Pydantic data models
│   ├── pipeline.py         # Main orchestration pipeline
│   ├── image_processor.py  # Image manipulation
│   ├── legal_checker.py    # Legal compliance engine
│   ├── storage.py          # Asset storage manager
│   ├── cli.py              # CLI interface
│   └── main.py             # Entry point
├── examples/
│   ├── campaigns/          # Example campaign briefs
│   ├── guidelines/         # Brand, legal, localization guides
│   └── logos/              # Example brand logos
├── tests/                  # Test suite
├── docs/                   # Documentation
├── output/                 # Generated assets
└── README.md              # This file
```

---

## 🛠️ Campaign Brief Generator

**New in v1.1.0:** Generate campaign briefs with enhanced prompt engineering strategies!

The `scripts/generate_campaign_brief.py` tool creates campaign briefs implementing advanced prompt optimization from the [IMAGE_QUALITY_OPTIMIZATION.md](docs/IMAGE_QUALITY_OPTIMIZATION.md) guide, resulting in **30-40% better image quality**.

### Quick Usage

```bash
# List available templates
python3 scripts/generate_campaign_brief.py --list-templates

# Generate premium audio campaign (earbuds + headphones)
python3 scripts/generate_campaign_brief.py --template premium_audio

# Generate premium tech campaign (earbuds + monitor)
python3 scripts/generate_campaign_brief.py --template premium_tech

# Generate fashion campaign (sneakers)
python3 scripts/generate_campaign_brief.py --template fashion
```

### Enhanced Features

Generated campaign briefs include:

- **Structured Prompts** - Professional photography terminology and composition rules
- **7 Category Templates** - Electronics, fashion, food, beauty, automotive, premium audio, display tech
- **Detailed Breakdowns** - Style, composition, lighting, background, and detail parameters
- **Negative Prompts** - Explicit guidance on what to avoid
- **Backend Optimization** - Optimized for Firefly, DALL-E 3, and Gemini Imagen 4

### Example Generated Structure

```json
{
  "enhanced_generation": {
    "style_parameters": {
      "photography_style": "commercial product photography",
      "mood": "premium luxury",
      "quality_level": "ultra high resolution 8K"
    },
    "composition": {
      "viewing_angle": "3/4 angle from above",
      "depth_of_field": "shallow DOF with sharp focus",
      "rule_of_thirds": true
    },
    "lighting": {
      "primary_light": "soft key light from 45 degrees",
      "rim_light": "strong rim light highlighting metallic edges",
      "color_temperature": "cool daylight 5500K"
    },
    "negative_prompt": "cheap appearance, flat lighting, cluttered, low resolution"
  }
}
```

See [scripts/README.md](scripts/README.md) for complete documentation.

---

## 🎯 Examples

### Example 1: Premium Tech Campaign (NEW!)

Generate assets for premium earbuds and portable monitor across 5 global markets:

```bash
./run_cli.sh examples/premium_tech_campaign.json firefly
```

**Output:**
- 2 premium products (Elite Wireless Earbuds Pro, UltraView 4K Monitor)
- 5 locales (US, Mexico, France, Germany, Japan)
- 3 aspect ratios per product
- **30 total assets** + 2 hero images + 2 per-product reports

**Directory Structure:**
```
output/
├── EARBUDS-001/
│   └── PREMIUM2026/
│       ├── hero/EARBUDS-001_hero.png
│       ├── en-US/, es-MX/, fr-FR/, de-DE/, ja-JP/
│       └── EARBUDS-001_campaign_report.json
└── MONITOR-001/
    └── PREMIUM2026/
        └── ...
```

### Example 2: Multi-Locale Campaign

Generate assets for US, Mexico, and France:

```bash
./run_cli.sh examples/campaigns/multi_locale_campaign.json
```

**Output:**
- 3 locales × 2 products × 3 aspect ratios = **18 assets**
- Culturally-adapted messaging per locale
- Brand-consistent visuals across all markets

### Example 3: Specify Backend

Run with different image generation backends:

```bash
# Use Adobe Firefly (commercial-safe, high quality)
./run_cli.sh examples/campaign_brief.json firefly

# Use OpenAI DALL-E 3 (creative, high quality)
./run_cli.sh examples/campaign_brief.json openai

# Use Google Gemini Imagen 4 (fast, high quality)
./run_cli.sh examples/campaign_brief.json gemini
```

### Example 4: Health Product with Legal Compliance

Generate FDA-compliant health product assets:

```bash
./run_cli.sh examples/campaigns/health_product_campaign.json
```

**Features:**
- Pre-generation legal compliance check
- Blocks prohibited claims (cure, treat, prevent)
- Requires FDA disclaimers
- Ensures regulatory compliance

### Example 5: Asset Reuse for Cost Savings

Reuse existing hero images, generate only new formats:

```bash
./run_cli.sh examples/campaigns/asset_reuse_campaign.json
```

**Benefits:**
- Fewer image-generation API calls (a cached hero is reused instead of regenerated)
- Faster processing for reused formats (no generation call)
- Lower spend follows directly from the avoided API calls

  (The exact reduction depends on your cache-hit rate; the per-run figures are
  reported in the technical metrics, not asserted as fixed percentages here.)

---

## 📊 Enhanced Campaign Reporting

**New in v1.3.0:** Technical metrics measured for every campaign run. (A former "business metrics" block was removed — see the note below.)

### Overview

Every campaign generates a detailed report in `output/campaign_reports/` with:
- **Technical Metrics** - API performance, cache efficiency, memory usage (measured per run)
- **Historical Tracking** - Timestamped reports for audit trails

> **Note:** Earlier versions of this README advertised a `business_metrics` block (ROI multiplier, dollar savings, time-saved-vs-manual). Those values were computed entirely from hard-coded constants and were tautologies, not measurements, so the code and the report no longer emit them. See [Roadmap → Honest business metrics](#-roadmap) for what real inputs would be required, and `docs/ENHANCED_REPORTING.md` for the full explanation.

### Report Location & Format

**Location:** `output/campaign_reports/`

**Filename Format:** `campaign_report_CAMPAIGN_ID_PRODUCT_ID_YYYY-MM-DD.json`

**Example:** `campaign_report_PREMIUM2026_EARBUDS-001_2026-01-19.json`

### Technical Metrics (17 fields)

```json
{
  "technical_metrics": {
    "backend_used": "firefly",
    "total_api_calls": 2,
    "cache_hits": 0,
    "cache_misses": 2,
    "cache_hit_rate": 0.0,
    "retry_count": 0,
    "retry_reasons": [],
    "avg_api_response_time_ms": 1250.5,
    "min_api_response_time_ms": 1100.0,
    "max_api_response_time_ms": 1401.0,
    "image_processing_time_ms": 3420.2,
    "localization_time_ms": 1150.3,
    "compliance_check_time_ms": 235.1,
    "peak_memory_mb": 342.5,
    "system_info": {
      "platform": "Darwin",
      "python_version": "3.11.5",
      "processor": "arm64"
    },
    "full_error_traces": []
  }
}
```

**What you can track:**
- API performance and response times
- Cache utilization and efficiency
- Retry attempts and failure reasons
- Processing time breakdowns
- Memory usage patterns
- System environment details
- Full error stack traces for debugging

### Business Metrics — removed (not currently computed)

A `business_metrics` block (ROI multiplier, cost-savings percentage, dollar
savings, time-saved-vs-manual hours) used to appear here. **It was removed
because every field was derived from hard-coded constants** (a fixed 96-hour
manual baseline and a fixed $2,700 manual cost), which made the reported "ROI
multiplier" algebraically fixed by construction regardless of the actual
workload. A number determined entirely by hard-coded inputs is a restatement of
the input, not a measurement, so the report no longer emits it. See
[Roadmap → Honest business metrics](#-roadmap).

### Console Output

When you run a campaign, you'll see comprehensive metrics:

```
✅ Campaign processing complete!
   Total assets generated: 30
   Processing time: 45.3 seconds
   Success rate: 100.0%
   Reports saved: 2 product reports

📊 Technical Metrics:
   Backend: firefly
   API Calls: 2 total, 0 cache hits (0.0% hit rate)
   API Response Time: 1250ms avg (1100-1400ms range)
   Image Processing: 3420ms total
   Localization: 1150ms total
   Compliance Check: 235ms
   Peak Memory: 342.5 MB
```

> The console output is limited to the **technical metrics measured during the
> run**. The pipeline no longer prints "Business Metrics" / ROI / dollar-savings
> lines — see [Roadmap → Honest business metrics](#-roadmap).

### Use Cases

**For Product Managers:**
- Monitor asset production efficiency (processing time, throughput)
- Track compliance pass rates across campaigns
- Identify optimization opportunities
- *(planned)* Cost/ROI tracking once real cost inputs are wired in — see [Roadmap](#-roadmap)

**For Engineers:**
- Monitor API performance and response times
- Track cache efficiency and optimization
- Debug errors with full stack traces
- Profile memory usage and system resources
- Identify performance bottlenecks

**For Finance Teams:** *(planned — not yet computed)*
- Cost-per-asset and cost savings vs. a manual baseline
- ROI analysis for AI automation investment
- Budget planning for campaign production

  These require real per-call API billing data, a measured manual-production
  baseline, and a cost-of-time input — none of which are wired in today. See
  [Roadmap → Honest business metrics](#-roadmap).

**For Compliance Officers:**
- Monitor compliance pass rates
- Track regulatory violations
- Audit historical campaign compliance
- Generate compliance reports for stakeholders

### Historical Tracking

Reports are **never overwritten** - each run creates a new timestamped report:

```
output/campaign_reports/
├── campaign_report_PREMIUM2026_EARBUDS-001_2026-01-19.json
├── campaign_report_PREMIUM2026_EARBUDS-001_2026-01-20.json
├── campaign_report_PREMIUM2026_MONITOR-001_2026-01-19.json
└── campaign_report_PREMIUM2026_MONITOR-001_2026-01-20.json
```

**Benefits:**
- Complete audit trail for all campaigns
- Track performance improvements over time
- Compare metrics across campaign iterations
- Historical compliance documentation

### Performance Impact

The enhanced reporting system adds minimal overhead:
- Memory tracking: ~5-10ms per product
- Metric calculation: ~15-20ms total
- **Total overhead: ~20-30ms per campaign** (negligible)

---

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for:

- Code of Conduct
- Development setup
- Coding standards
- Pull request process
- Testing requirements

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 📞 Support

- **Documentation:** [Full Docs](docs/)
- **Issues:** [GitHub Issues](https://github.com/yourusername/adobe-genai-project/issues)
- **Discussions:** [GitHub Discussions](https://github.com/yourusername/adobe-genai-project/discussions)

---

## 🗺️ Roadmap

### Current Version: 1.3.0

### ✅ Completed Features (v1.0 - v1.3)

- ✅ **Legal Compliance System** - FTC, FDA, SEC/FINRA regulatory frameworks
- ✅ **Multi-Backend AI** - Firefly, DALL-E 3, Gemini integration
- ✅ **AI Localization** - 40+ languages with Claude 3.5 Sonnet
- ✅ **Phase 1 Innovation** - Per-element text customization (patent-pending)
- ✅ **Brand Guidelines** - Comprehensive enforcement system
- ✅ **Asset Optimization** - Hero image reuse via caching (fewer API calls)
- ✅ **Campaign Reporting** - Technical metrics (measured) + timestamped historical reports

### In Progress (delivered later in the correctness/feature plan)

- 🔶 **Native multi-format generation** - Opt-in via `native_aspect_ratios`: the pipeline requests each ratio (1:1 / 9:16 / 16:9 / 4:5) natively using per-backend ratio→size maps (one paid call per ratio). The default remains a single square hero cropped to each ratio. Marked in progress until native output is verified against a live backend (post-Firefly-auth, P2-T1).
- 🔶 **Real cost & API-call metrics** - The API metrics endpoints currently return placeholder zeros for `api_calls`, `cache_hit_rate`, and `cost_estimate_usd`; real instrumentation is being wired in.
- 🔶 **Live WebSocket progress** - Real-time job progress over WebSocket. The current implementation emits a fixed heartbeat, not true per-step progress.

#### Honest business metrics *(planned — not yet computed)*

A `business_metrics` block (ROI multiplier, dollar savings, time-saved-vs-manual)
was **removed** because its values were tautologies derived from hard-coded
constants, not measurements. To compute these honestly the pipeline would need
three real inputs that are not wired in today:

1. **Real per-call API cost** — from each provider's billing API, or a configurable per-backend rate card.
2. **A measured manual-production baseline** — observed time and cost from a real comparable manual workflow at the deploying organization.
3. **A defined cost-of-time input** — a fully-loaded hourly rate for the relevant role, supplied per deployment.

With those, the pipeline could honestly report cost-per-asset, time-per-asset,
and a delta vs. the organization's own baseline. Until then, no ROI or
dollar-savings figure is emitted. See `docs/ENHANCED_REPORTING.md`.

### Planned Features (v1.4+)

- [ ] **Video Generation** - Extend to video asset generation
- [ ] **Interactive Previews** - Web UI for campaign preview
- [ ] **A/B Testing** - Generate variants for testing
- [ ] **Performance Analytics** - Track asset performance
- [ ] **Template Library** - Pre-built campaign templates
- [ ] **API Server** - RESTful API for integrations
- [ ] **Additional Compliance** - GDPR, CCPA, international regulations
- [ ] **Compliance Reporting** - Export compliance reports for legal teams

---

<div align="center">

**[⬆ back to top](#adobe-genai-creative-automation-platform)**

Made with ❤️ by the Adobe GenAI Team

</div>
# adobe-genai-project
# adobe-genai-project
# adobe-genai-project
# adobe-genai-project
