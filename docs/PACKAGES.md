# Package Summaries

## src/

### Core Modules

#### `src/models.py` (~500 lines)
**Pydantic data models** for all data structures.

**Key Classes:**
- `CampaignBrief` - Campaign configuration
- `Product` - Product information
- `CampaignMessage` - Marketing message
- `ComprehensiveBrandGuidelines` - Brand guidelines model
- `LocalizationGuidelines` - Localization rules
- `LegalComplianceGuidelines` - Legal compliance rules
- `GeneratedAsset` - Asset metadata
- `CampaignOutput` - Campaign results

**Dependencies:** pydantic

---

#### `src/pipeline.py` (~400 lines)
**Main orchestrator** for campaign processing.

**Key Class:**
- `CreativeAutomationPipeline` - Coordinates all operations

**Key Methods:**
- `process_campaign()` - Main entry point
- `_load_guidelines()` - Load external guidelines
- `_check_legal_compliance()` - Pre-generation validation
- `_process_product()` - Per-product processing

**Dependencies:** asyncio, models, genai, parsers, image_processor, legal_checker, storage

---

#### `src/cli.py` (~200 lines)
**Command-line interface** using Click framework.

**Commands:**
- `process` - Process campaign
- `validate-config` - Validate environment
- `list-examples` - List example campaigns

**Dependencies:** click, pipeline, models

---

#### `src/main.py` (~50 lines)
**Entry point** for CLI execution.

**Dependencies:** cli

---

### GenAI Package (`src/genai/`)

#### `src/genai/factory.py` (~50 lines)
**Factory pattern** for image generation backend selection.

**Key Function:**
- `ImageGenerationFactory.create()` - Returns appropriate service

**Supported Backends:** firefly, openai, dalle, gemini, imagen

---

#### `src/genai/firefly.py` (~200 lines)
**Adobe Firefly integration**.

**Key Class:**
- `FireflyImageService` - Firefly Image 3 API client

**Methods:**
- `generate_image()` - Generate image from prompt
- `get_backend_name()` - Return "Adobe Firefly"

**API:** REST with OAuth2

---

#### `src/genai/openai_client.py` (~150 lines)
**OpenAI DALL-E 3 integration**.

**Key Class:**
- `OpenAIImageService` - DALL-E 3 API client

**Methods:**
- `generate_image()` - Generate image from prompt
- `get_backend_name()` - Return "OpenAI DALL-E 3"

**API:** REST with Bearer token

---

#### `src/genai/gemini.py` (~200 lines)
**Google Gemini Imagen 4 integration**.

**Key Class:**
- `GeminiImageService` - Imagen 4 API client

**Methods:**
- `generate_image()` - Generate image from prompt
- `get_backend_name()` - Return "Google Gemini Imagen 4"

**API:** Google AI Studio REST API

---

#### `src/genai/claude.py` (~300 lines)
**Anthropic Claude integration** for localization.

**Key Class:**
- `ClaudeService` - Claude 3.5 Sonnet client

**Methods:**
- `extract_brand_guidelines()` - Parse guideline documents
- `localize_message()` - Translate with cultural adaptation
- `_call_claude()` - API wrapper with retry

**Model:** claude-sonnet-4-20250514

---

### Parsers Package (`src/parsers/`)

#### `src/parsers/brand_parser.py` (~200 lines)
**Brand guidelines parser**.

**Key Class:**
- `BrandGuidelinesParser` - Extract brand guidelines

**Methods:**
- `parse()` - Parse from PDF/DOCX/MD
- `_extract_pdf()` - PDF text extraction
- `_extract_docx()` - DOCX text extraction

**Supported Formats:** PDF, DOCX, MD, YAML, JSON

---

#### `src/parsers/localization_parser.py` (~100 lines)
**Localization guidelines parser**.

**Key Class:**
- `LocalizationGuidelinesParser` - Parse localization rules

**Methods:**
- `parse()` - Parse from YAML/JSON

**Supported Formats:** YAML, JSON

---

#### `src/parsers/legal_parser.py` (~50 lines)
**Legal compliance guidelines parser**.

**Key Class:**
- `LegalComplianceParser` - Parse legal guidelines

**Methods:**
- `parse()` - Parse from YAML/JSON

**Supported Formats:** YAML, JSON

---

### `src/image_processor.py` (~400 lines)
**Image manipulation and overlay** using Pillow.

**Key Class:**
- `ImageProcessor` - Image processing operations

**Methods:**
- `resize_to_aspect_ratio()` - Smart resize with aspect ratio
- `apply_text_overlay()` - Render text with brand guidelines
- `apply_logo_overlay()` - Position logo in corners
- `_calculate_text_position()` - Text layout algorithm
- `_calculate_logo_position()` - Logo placement algorithm

**Dependencies:** PIL (Pillow)

---

### `src/legal_checker.py` (~350 lines)
**Legal compliance validation engine**.

**Key Classes:**
- `ComplianceViolation` - Violation data class
- `LegalComplianceChecker` - Compliance validator

**Methods:**
- `check_content()` - Main validation entry
- `_check_text()` - Text field validation
- `_word_exists()` - Whole-word matching (regex)
- `generate_report()` - Human-readable report
- `get_violation_summary()` - Statistics

**Severity Levels:** error, warning, info

---

### `src/storage.py` (~300 lines)
**Asset storage and management**.

**Key Class:**
- `StorageManager` - File system operations

**Methods:**
- `create_campaign_directory()` - Setup directory structure
- `get_asset_path()` - Generate asset paths
- `save_image()` - Save PIL image to file
- `save_report()` - Generate JSON report
- `backup_campaign_brief()` - Backup original brief
- `update_campaign_brief()` - Update brief with asset paths

**Directory Structure:**
```
output/
└── {product_id}/
    └── {campaign_id}/
        ├── hero/
        │   └── {product_id}_hero.png
        ├── {locale}/
        │   └── {ratio}/
        │       └── {product_id}_{ratio}_{locale}.{format}
        └── {product_id}_campaign_report.json
```

---

## tests/

### `tests/test_models.py` (~200 lines)
Unit tests for Pydantic models.

**Coverage:** Model validation, field constraints, defaults

---

### `tests/test_pipeline.py` (~300 lines)
Integration tests for pipeline orchestration.

**Coverage:** End-to-end campaign processing, error handling

---

### `tests/test_image_processor.py` (~250 lines)
Unit tests for image manipulation.

**Coverage:** Resizing, overlays, text rendering, logo placement

---

### `tests/test_legal_checker.py` (~200 lines)
Unit tests for legal compliance.

**Coverage:** Violation detection, severity classification, reporting

---

### `tests/test_parsers.py` (~150 lines)
Unit tests for guideline parsers.

**Coverage:** PDF/DOCX parsing, YAML/JSON parsing

---

## examples/

### `examples/campaigns/` - Example Campaign Briefs
- `campaign_brief.json` - Basic multi-product campaign
- `multi_locale_campaign.json` - Multiple locales
- `test_legal_compliance.json` - Non-compliant example
- `test_legal_compliance_compliant.json` - Compliant example

---

### `examples/guidelines/` - Configuration Files

#### Brand Guidelines
- `brand_guidelines.yaml` - Complete brand guidelines
- `brand_no_shadow.yaml` - Without text shadows
- `brand_with_logo.yaml` - With logo configuration

#### Localization
- `localization_rules.yaml` - Localization guidelines

#### Legal Compliance
- `legal_compliance_general.yaml` - General products (FTC)
- `legal_compliance_health.yaml` - Health products (FDA)
- `legal_compliance_financial.yaml` - Financial (SEC/FINRA)

#### Documentation
- `LEGAL_COMPLIANCE.md` (600+ lines) - Legal system guide
- `LEGAL_EXAMPLES.md` (300+ lines) - Violation examples

---

### `examples/logos/` - Brand Logos
Example logo files for testing logo placement feature.

---

## docs/

### Core Documentation
- `API.md` - API reference
- `PACKAGES.md` - This file
- `TEXT_CUSTOMIZATION.md` - Text customization guide
- `LOGO_PLACEMENT.md` - Logo placement guide
- `LEGAL_COMPLIANCE_IMPLEMENTATION.md` - Legal system implementation

---

## Root Files

### Configuration
- `.env.example` - Environment template
- `.gitignore` - Git exclusions
- `requirements.txt` - Python dependencies
- `requirements-dev.txt` - Development dependencies

### Documentation
- `README.md` - Project overview
- `ARCHITECTURE.md` - System design
- `FEATURES.md` - Feature matrix
- `QUICKSTART.md` - Quick start guide
- `CONTRIBUTING.md` - Development guidelines
- `CHANGELOG.md` - Version history
- `LICENSE` - MIT License

### Scripts
- `run_cli.sh` - CLI wrapper script

---

## Dependencies

### Core Dependencies
```txt
anthropic>=0.40.0       # Claude API
openai>=1.60.0          # OpenAI API
google-generativeai     # Gemini API
Pillow>=10.0.0          # Image processing
pydantic>=2.10.0        # Data validation
python-dotenv>=1.0.0    # Environment management
click>=8.1.0            # CLI framework
aiohttp>=3.11.0         # Async HTTP
PyYAML>=6.0            # YAML parsing
```

### Development Dependencies
```txt
pytest>=8.0.0          # Testing
pytest-cov>=4.1.0      # Coverage
pytest-asyncio>=0.21.0 # Async testing
black>=24.0.0          # Code formatting
flake8>=7.0.0          # Linting
mypy>=1.8.0            # Type checking
pre-commit>=3.5.0      # Git hooks
```

---

## Code Statistics

| Metric | Value |
|--------|-------|
| **Total Lines** | ~5,000+ |
| **Source Files** | 20+ |
| **Test Files** | 10+ |
| **Documentation** | 15+ files |
| **Examples** | 10+ |
| **Test Coverage** | ≥80% |

---

## Module Dependencies

```
src/
├── cli.py
│   └── pipeline.py
│       ├── models.py
│       ├── genai/
│       │   ├── factory.py
│       │   ├── firefly.py
│       │   ├── openai_client.py
│       │   ├── gemini.py
│       │   └── claude.py
│       ├── parsers/
│       │   ├── brand_parser.py
│       │   ├── localization_parser.py
│       │   └── legal_parser.py
│       ├── image_processor.py
│       ├── legal_checker.py
│       └── storage.py
└── main.py
    └── cli.py
```

---

## Architecture Patterns

| Package | Pattern Used |
|---------|-------------|
| `genai/factory.py` | Factory Pattern |
| `image_processor.py` | Strategy Pattern |
| `models.py` | Builder Pattern (Pydantic) |
| `parsers/` | Template Method |
| `pipeline.py` | Orchestrator Pattern |

---

## Related Documentation

- **[ARCHITECTURE.md](../ARCHITECTURE.md)** - System architecture
- **[API.md](API.md)** - API documentation
- **[README.md](../README.md)** - Project overview
