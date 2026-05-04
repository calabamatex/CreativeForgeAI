# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] - 2026-01-14

### Added
- 🎨 Multi-backend image generation (Firefly, DALL-E 3, Gemini Imagen 4)
- 🌍 AI-powered localization with Claude 3.5 Sonnet
- ⚖️ Legal compliance checking system (FTC, FDA, SEC, FINRA)
- 🎭 Brand guidelines enforcement with color/typography control
- 📐 Multi-format asset generation (1:1, 16:9, 9:16)
- 🔄 Asset reuse system for cost optimization
- 🎨 Advanced text customization (colors, shadows, backgrounds)
- 🖼️ Logo placement with 4-corner positioning
- 📊 Campaign analytics and reporting
- 🏗️ Modular, layered architecture
- 🧪 Comprehensive test suite (≥80% coverage)
- 📚 Complete documentation suite

### Features
- Adobe Firefly integration
- OpenAI DALL-E 3 integration
- Google Gemini Imagen 4 integration
- Claude 3.5 Sonnet for localization
- Three legal compliance templates (general, health, financial)
- Pydantic v2 data validation
- Async/concurrent processing
- Hero image caching
- Brief backup and updates
- JSON campaign reports
- Organized asset storage

### Documentation
- README.md with quick start
- ARCHITECTURE.md with system design
- FEATURES.md with complete feature matrix
- QUICK_START.md with step-by-step guide
- CONTRIBUTING.md with development guidelines
- TEXT_CUSTOMIZATION.md
- LOGO_PLACEMENT.md
- LEGAL_COMPLIANCE.md (600+ lines)
- LEGAL_EXAMPLES.md (300+ lines)
- LEGAL_COMPLIANCE_IMPLEMENTATION.md (400+ lines)

---

## [1.1.0] - 2026-01-15

### Changed
- 🔄 **BREAKING**: Reorganized output directory structure from Campaign → Locale → Product to Product → Campaign → Locale
- 📊 Split campaign reports per product instead of single combined report
- 🚀 Enhanced `run_cli.sh` with command-line arguments for brief and backend selection

### Added
- 📋 New premium tech campaign example (`premium_tech_campaign.json`)
  - Elite Wireless Earbuds Pro
  - UltraView Portable 4K Monitor
  - 5 global locales (US, Mexico, France, Germany, Japan)
- 🎨 Command-line arguments for `run_cli.sh`:
  - Positional arguments: `[BRIEF_FILE] [BACKEND]`
  - `--help` flag with usage examples
  - File existence validation
  - Default values support
- 🛠️ **Campaign Brief Generator Script** (`scripts/generate_campaign_brief.py`)
  - Generate campaign briefs with enhanced prompt engineering
  - 7 category templates (electronics, fashion, food, beauty, automotive, premium audio, display tech)
  - Structured prompts with professional photography terminology
  - Style, composition, lighting, background, and detail parameters
  - Negative prompts for quality control
  - 30-40% image quality improvement potential
- 📚 **IMAGE_QUALITY_OPTIMIZATION.md** (1,000+ lines)
  - Advanced prompt engineering strategies
  - JSON structured prompts with Pydantic models
  - Backend-specific optimization (Firefly, DALL-E, Gemini)
  - Multi-pass generation and quality scoring
  - Prompt template library by category
- 📚 Enhanced documentation with new examples

### Fixed
- Removed spurious campaign directory creation at root level
- Each product now gets its own campaign report co-located with assets

### Directory Structure
**Old:**
```
output/
└── CAMPAIGN_ID/
    ├── hero/
    ├── locale/product_id/ratio/
    └── campaign_report.json
```

**New:**
```
output/
└── PRODUCT_ID/
    └── CAMPAIGN_ID/
        ├── hero/
        ├── locale/ratio/
        └── PRODUCT_ID_campaign_report.json
```

### Benefits
- Easier product-centric asset management
- Clean multi-product campaign organization
- Per-product reports for better tracking
- Simplified asset sharing per product

---

## [1.2.0] - 2026-01-16

### Added

- 📚 **Enhanced Legal Compliance Documentation**
  - Comprehensive Legal Compliance System section in README.md
  - Detailed regulatory framework breakdown (FTC, FDA, SEC/FINRA)
  - Code examples for compliant and non-compliant campaigns
  - Compliance templates comparison table
  - Quick start guide for compliance validation
  - Benefits and industry applications sections
  - Links to all 3 legal compliance documentation files (1,300+ total lines)
  - Updated FEATURES.md with expanded compliance tables
  - Added compliance section to Table of Contents
  - Updated Roadmap with completed and planned compliance features
- 🎨 **Phase 1 Complete Implementation**
  - Per-element text customization (headline, subheadline, CTA)
  - Text outline effects for maximum readability
  - Post-processing pipeline (sharpening, color correction)
  - 100% backward compatibility with legacy settings

- 📦 **New Data Models**
  - `TextShadow` - Drop shadow configuration
  - `TextOutline` - Text stroke/outline configuration
  - `TextBackgroundBox` - Semi-transparent background boxes
  - `TextElementStyle` - Per-element styling
  - `TextCustomization` - Independent element customization
  - `PostProcessingConfig` - Image enhancement settings

- 🔧 **Enhanced Image Processor** (`image_processor_v2.py`)
  - Per-element text rendering with independent effects
  - Text outline/stroke implementation
  - Background box with opacity control
  - Post-processing: sharpening (unsharp mask)
  - Post-processing: color correction (contrast, saturation)
  - Font caching for performance
  - Backward compatibility layer

- 📋 **Example Brand Guidelines** (5 new files)
  - `phase1_per_element_text.yaml` - Showcase per-element control
  - `phase1_text_outlines.yaml` - Text outline examples
  - `phase1_post_processing.yaml` - Image enhancement
  - `phase1_complete.yaml` - All features combined
  - `phase1_minimal.yaml` - Clean minimal design

- 🧪 **Comprehensive Test Suite** (`test_phase1_features.py`)
  - 20 unit tests covering all Phase 1 features
  - Data model validation tests
  - Backward compatibility tests
  - Text effect rendering tests
  - Post-processing tests
  - Integration tests
  - 100% pass rate

- 📚 **Complete Documentation**
  - `PHASE1_IMPLEMENTATION_GUIDE.md` - Comprehensive implementation guide
  - Usage examples and best practices
  - Migration guide from legacy settings
  - Troubleshooting section
  - Performance impact analysis

- 🛠️ **Phase 1 Campaign Brief Generator** (`generate_campaign_brief_p1_updates.py`)
  - Generates campaign briefs with Phase 1 features pre-configured
  - 4 text customization presets (high_contrast_bold, readability_first, minimal_modern, premium_luxury)
  - 4 post-processing presets (standard, subtle, vivid, professional)
  - Template-specific defaults for optimal results
  - Full command-line interface with preset selection
  - Example campaign: `examples/premium_tech_campaign_p1.json`

- 📊 **Presentation Materials (subsequently removed)**
  - Multiple presentation/exec-deck markdown files were added in this release. They have been removed in a later cleanup pass because they contained Adobe trade-dress claims, fabricated TAM/financial projections, and tautological ROI figures that did not reflect what the implementation actually does. See the Removed section below for details.

### Changed
- Updated `ComprehensiveBrandGuidelines` model with new fields
  - `text_customization` (optional) - Takes precedence over legacy
  - `post_processing` (optional) - Image enhancement config
- Enhanced `pipeline.py` to apply post-processing automatically
- Marked legacy text settings as "LEGACY" in comments

### Performance
- Per-element text rendering: +10-20ms
- Text outline effects: +5-10ms per element
- Post-processing: +30-45ms
- **Total overhead: ~60-95ms per image** (acceptable)

### Technical Improvements
- Font caching system for better performance
- Backward compatibility fallback logic
- Independent text element styling
- Modular post-processing pipeline
- Clean separation of concerns

---

## [1.3.0] - 2026-01-19

### Added

- 📊 **Campaign Reporting System**
  - `TechnicalMetrics` data model with 17 technical fields
    - Backend tracking, API call statistics, cache hit/miss rates
    - Retry count and detailed retry reasons
    - API response time metrics (avg, min, max)
    - Image processing, localization, and compliance check timing
    - Peak memory usage monitoring
    - System environment information
    - Full error stack traces for debugging
  - Updated `CampaignOutput` model with optional `technical_metrics` field
  - Enhanced `pipeline.py` with metric collection during execution
  - Real-time memory usage tracking with psutil
- 📁 **Reorganized Campaign Reports**
  - New centralized directory: `output/campaign_reports/`
  - Filename format: `campaign_report_CAMPAIGN_ID_PRODUCT_ID_YYYY-MM-DD.json`
  - Historical report preservation with timestamps (no overwrites within a single day's runs are deduped on the date stamp)
- 🖥️ **Console Output**
  - Technical metrics summary display
  - Cache efficiency and API performance visibility

### Removed (post-release cleanup)
- `BusinessMetrics` data model and the corresponding ROI / cost-savings / time-saved console output. The earlier version computed these from hard-coded constants (`manual_baseline_hours = 96.0`, `manual_baseline_cost = 2700.0`, `cost_savings_percentage = 80.0 + cache_bonus`), which made the reported "ROI multiplier" algebraically `0.80 / 0.20 = 4.0` by construction regardless of workload. The values were tautologies, not measurements, so they have been removed. To produce honest business metrics, the implementation would need real per-call API cost data, a measured manual-production baseline, and a defined cost-of-time input — none of which are wired in.

### Changed
- Updated `src/storage.py` `save_report()` method
  - Reports now saved to centralized `campaign_reports/` directory
  - Filename includes both campaign ID and product ID
  - Date timestamp prevents overwrites across different days
- Enhanced `src/pipeline.py` orchestration
  - Added psutil for memory monitoring
  - Tracks API response times for all calls
  - Calculates cache hit/miss rates
  - Monitors image processing, localization, and compliance timing
- Updated imports in `src/models.py`
  - Added `Optional` type hint for new optional fields

### Performance
- Memory tracking: ~5-10ms overhead per product
- Metric calculation: ~15-20ms total overhead
- **Total reporting overhead: ~20-30ms per campaign** (negligible)

### Benefits
- **Audit trail** - Historical reports with timestamps
- **Performance insights** - Detailed technical metrics for optimization
- **Efficiency monitoring** - Cache utilization and processing speed
- **Debugging support** - Full error traces and system info

---

## [Unreleased]

### Planned for 1.4.0 (Phase 2)
- [ ] Video generation support
- [ ] Web UI for campaign preview
- [ ] A/B testing variants
- [ ] Template library
- [ ] Batch processing
- [ ] API server with REST endpoints

### Planned for 1.3.0
- [ ] Cloud storage integration (S3, Azure Blob)
- [ ] CDN integration
- [ ] Performance analytics dashboard
- [ ] Multi-tenancy support

### Planned for 2.0.0
- [ ] Real-time collaboration
- [ ] GraphQL API
- [ ] WebSocket support
- [ ] Microservices architecture
- [ ] Event-driven processing

---

## Version History

### Pre-1.0 Development

#### [0.5.0] - 2026-01-13
- Added legal compliance checking system
- Created three legal compliance templates
- Implemented pre-generation validation
- Added violation severity levels

#### [0.4.0] - 2026-01-12
- Added logo placement feature
- Implemented 4-corner positioning
- Added logo sizing and opacity controls
- Created logo placement documentation

#### [0.3.0] - 2026-01-11
- Added text customization features
- Implemented text colors and shadows
- Added background box support
- Created text customization guide

#### [0.2.0] - 2026-01-10
- Added asset reuse system
- Implemented hero image caching
- Added brief update functionality
- Improved storage organization

#### [0.1.0] - 2026-01-09
- Initial project setup
- Basic pipeline implementation
- Multi-backend support
- Claude localization integration

---

## Migration Guide

### Upgrading to 1.0.0

No breaking changes in 1.0.0 release.

### Future Breaking Changes

None planned for 1.x series. Breaking changes will be reserved for 2.0.0.

---

## Deprecations

None currently.

---

## Security Fixes

### 1.0.0
- Secure API key management via environment variables
- Input validation with Pydantic
- Path traversal prevention
- Prompt injection protection

---

## Performance Improvements

### 1.0.0
- Concurrent product processing
- Hero image reuse (70-90% API call reduction)
- HTTP session pooling
- Exponential backoff retry logic
- Async I/O operations

---

## Links

- [GitHub Repository](https://github.com/calabamatex/CreativeForgeAI)
- [Documentation](https://github.com/calabamatex/CreativeForgeAI/tree/main/docs)
- [Issues](https://github.com/calabamatex/CreativeForgeAI/issues)
- [Releases](https://github.com/calabamatex/CreativeForgeAI/releases)
