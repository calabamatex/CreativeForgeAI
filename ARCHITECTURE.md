# Architecture Documentation

## System Overview

The Creative Automation Pipeline is built on a modular, layered architecture that separates concerns and enables flexible extension.

## High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        Presentation Layer                         │
│  ┌──────────────┐         ┌──────────────┐                       │
│  │  CLI (Click) │         │  run_cli.sh  │                       │
│  └──────┬───────┘         └──────┬───────┘                       │
└─────────┼────────────────────────┼───────────────────────────────┘
          │                        │
┌─────────▼────────────────────────▼───────────────────────────────┐
│                      Application Layer                            │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │          CreativeAutomationPipeline                      │    │
│  │  • Campaign orchestration                                │    │
│  │  • Guideline loading                                     │    │
│  │  • Legal compliance checking                             │    │
│  │  • Concurrent product processing                         │    │
│  └──┬──────────────┬──────────────┬─────────────┬─────────┘    │
└─────┼──────────────┼──────────────┼─────────────┼──────────────┘
      │              │              │             │
┌─────▼──────────────▼──────────────▼─────────────▼──────────────┐
│                      Business Logic Layer                        │
│  ┌──────────┐   ┌───────────────┐   ┌──────────────────────┐  │
│  │  Image   │   │     Legal     │   │   Parsers            │  │
│  │Processor │   │   Checker     │   │ • Brand Parser       │  │
│  │          │   │               │   │ • Legal Parser       │  │
│  │• Resize  │   │• Validation   │   │ • Locale Parser      │  │
│  │• Overlay │   │• Reporting    │   └──────────────────────┘  │
│  │• Logo    │   └───────────────┘                              │
│  └──────────┘                                                   │
└─────┬──────────────┬──────────────┬─────────────┬──────────────┘
      │              │              │             │
┌─────▼──────────────▼──────────────▼─────────────▼──────────────┐
│                      Integration Layer                           │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │          Image Generation Factory                         │  │
│  │  ┌──────────┐  ┌──────────┐  ┌───────────┐             │  │
│  │  │ Firefly  │  │  DALL-E  │  │  Gemini   │             │  │
│  │  └──────────┘  └──────────┘  └───────────┘             │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │          ClaudeService (Localization)                     │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────┬──────────────┬──────────────┬─────────────┬──────────────┘
      │              │              │             │
┌─────▼──────────────▼──────────────▼─────────────▼──────────────┐
│                         Data Layer                               │
│  ┌──────────────┐   ┌─────────────┐   ┌────────────────────┐  │
│  │   Pydantic   │   │   Storage   │   │   JSON/YAML        │  │
│  │   Models     │   │   Manager   │   │   Parsers          │  │
│  └──────────────┘   └─────────────┘   └────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Component Descriptions

### 1. Presentation Layer

#### CLI Interface (`src/cli.py`)
- **Technology:** Click framework
- **Responsibilities:**
  - Command-line argument parsing
  - User interaction
  - Progress reporting
  - Error display
- **Commands:**
  - `process` - Main campaign processing
  - `validate-config` - Configuration validation
  - `list-examples` - List example campaigns

#### Shell Wrapper (`run_cli.sh`)
- **Purpose:** Simplify execution with venv activation
- **Responsibilities:**
  - Virtual environment activation
  - CLI command execution
  - Environment cleanup

---

### 2. Application Layer

#### CreativeAutomationPipeline (`src/pipeline.py`)
- **Central orchestrator** for all campaign operations
- **Key Methods:**
  - `process_campaign()` - Main entry point
  - `_load_guidelines()` - Load external guidelines
  - `_check_legal_compliance()` - Pre-generation validation
  - `_process_product()` - Per-product asset generation
  - `_generate_report()` - Campaign summary creation

**Processing Flow:**
```
1. Load campaign brief
2. Backup original brief
3. Initialize image backend
4. Load brand guidelines
5. Load localization guidelines
6. Load legal compliance guidelines
7. Run legal compliance check
8. For each product:
   a. Generate/load hero image
   b. For each locale:
      - Localize message (if needed)
      - For each aspect ratio:
        * Resize hero image
        * Apply text overlay
        * Apply logo overlay
        * Save asset
9. Generate campaign report
10. Update campaign brief with asset paths
```

---

### 3. Business Logic Layer

#### ImageProcessor (`src/image_processor.py`)
- **Responsibilities:**
  - Image resizing with aspect ratio preservation
  - Text overlay with brand guidelines
  - Logo overlay with positioning
  - Background application
  - Shadow effects

**Key Methods:**
- `resize_to_aspect_ratio()` - Smart cropping/padding
- `apply_text_overlay()` - Renders text with brand fonts/colors
- `apply_logo_overlay()` - Positions logo in 4 corners
- `_calculate_text_position()` - Text layout algorithm
- `_calculate_logo_position()` - Logo placement algorithm

#### LegalComplianceChecker (`src/legal_checker.py`)
- **Responsibilities:**
  - Content validation against regulations
  - Violation detection and categorization
  - Compliance reporting

**Key Methods:**
- `check_content()` - Main validation entry point
- `_check_text()` - Text field validation
- `_word_exists()` - Whole-word matching
- `generate_report()` - Human-readable report
- `get_violation_summary()` - Statistics

**Severity Levels:**
- `ERROR` - Blocks campaign generation
- `WARNING` - Advisory, allows proceeding
- `INFO` - Informational reminders

#### Parsers (`src/parsers/`)

**BrandGuidelinesParser:**
- Extracts brand guidelines from PDF/DOCX/MD
- Uses Claude API for intelligent parsing
- Structured output via Pydantic models

**LocalizationGuidelinesParser:**
- Parses localization rules (YAML/JSON)
- Defines locale-specific adaptations
- Cultural context guidelines

**LegalComplianceParser:**
- Parses legal compliance guidelines (YAML/JSON)
- Industry-specific templates (general, health, financial)
- Locale-specific regulations

---

### 4. Integration Layer

#### Image Generation Factory (`src/genai/factory.py`)
**Factory Pattern** for backend abstraction

```python
@staticmethod
def create(backend: str) -> ImageGenerationService:
    backends = {
        'firefly': FireflyImageService,
        'openai': OpenAIImageService,
        'dalle': OpenAIImageService,
        'gemini': GeminiImageService,
        'imagen': GeminiImageService
    }
    return backends[backend]()
```

**Supported Backends:**

1. **Adobe Firefly** (`src/genai/firefly.py`)
   - Model: Firefly Image 3
   - API: REST with OAuth
   - Strengths: Commercially-safe, brand-consistent

2. **OpenAI DALL-E 3** (`src/genai/openai_client.py`)
   - Model: dall-e-3
   - API: REST with Bearer token
   - Strengths: High quality, creative

3. **Google Gemini Imagen 4** (`src/genai/gemini.py`)
   - Model: imagen-4.0-generate-001
   - API: Google AI Studio
   - Strengths: Latest Google AI, fast

#### ClaudeService (`src/genai/claude.py`)
- **Model:** Claude 3.5 Sonnet
- **Use Cases:**
  1. **Guideline Extraction** - Parse PDF/DOCX guidelines
  2. **Message Localization** - Culturally-adapted translation
  3. **Cultural Context** - Tone and sentiment preservation

**Key Methods:**
- `extract_brand_guidelines()` - Parse brand documents
- `localize_message()` - Translate with cultural adaptation
- `_call_claude()` - API wrapper with retry logic

---

### 5. Data Layer

#### Pydantic Models (`src/models.py`)

**Core Models:**

```python
CampaignBrief
├── campaign_id: str
├── campaign_name: str
├── brand_name: str
├── campaign_message: CampaignMessage
├── products: List[Product]
├── target_locales: List[str]
├── aspect_ratios: List[str]
├── brand_guidelines_file: str (optional)
├── localization_guidelines_file: str (optional)
└── legal_compliance_file: str (optional)

Product
├── product_id: str
├── product_name: str
├── product_description: str
├── product_category: str
├── key_features: List[str]
├── generation_prompt: str
└── existing_assets: Dict (optional)

ComprehensiveBrandGuidelines
├── brand_name: str
├── primary_color: str
├── secondary_color: str
├── text_color: str
├── text_shadow: bool
├── text_shadow_color: str
├── text_background: bool
├── logo_placement: str
└── logo_scale: float

LegalComplianceGuidelines
├── prohibited_words: List[str]
├── prohibited_phrases: List[str]
├── prohibited_claims: List[str]
├── restricted_terms: Dict
├── required_disclaimers: Dict
└── locale_restrictions: Dict
```

#### Storage Manager (`src/storage.py`)
- **Responsibilities:**
  - Asset organization (Campaign/Locale/Product/Format)
  - Report generation (JSON)
  - Brief backup and updates
  - Path management

**Directory Structure:**
```
output/
└── {product_id}/
    └── {campaign_id}/
        ├── hero/
        │   └── {product_id}_hero.png
        ├── {locale}/
        │   ├── 1x1/
        │   │   └── {product_id}_1x1_{locale}.png
        │   ├── 16x9/
        │   │   └── {product_id}_16x9_{locale}.png
        │   └── 9x16/
        │       └── {product_id}_9x16_{locale}.png
        └── {product_id}_campaign_report.json
```

---

## Design Patterns

### 1. Factory Pattern
**Where:** Image Generation Factory
**Why:** Abstract backend selection, enable runtime switching

### 2. Strategy Pattern
**Where:** Image processing (resize, overlay)
**Why:** Different strategies for different aspect ratios

### 3. Builder Pattern
**Where:** Pydantic models
**Why:** Complex object construction with validation

### 4. Template Method
**Where:** Parsers (BrandGuidelinesParser base)
**Why:** Common parsing structure, specialized implementations

### 5. Observer Pattern
**Where:** Progress reporting
**Why:** Decouple processing from UI updates

---

## Data Flow

### 1. Campaign Brief → Asset Generation

```
Campaign Brief (JSON)
    ↓
Load & Validate (Pydantic)
    ↓
Load Guidelines (Parsers)
    ↓
Legal Compliance Check (LegalChecker)
    ↓ (if compliant)
Select Image Backend (Factory)
    ↓
Generate Hero Image (AI Backend)
    ↓
For each (product, locale, aspect_ratio):
    ↓
    Localize Message (Claude)
    ↓
    Resize Image (ImageProcessor)
    ↓
    Apply Text Overlay (ImageProcessor)
    ↓
    Apply Logo Overlay (ImageProcessor)
    ↓
    Save Asset (StorageManager)
    ↓
Generate Report (StorageManager)
    ↓
Update Campaign Brief (StorageManager)
```

### 2. Legal Compliance Checking

```
Campaign Brief
    ↓
Load Legal Guidelines (YAML/JSON)
    ↓
For each text field:
    ↓
    Check prohibited words (regex \b boundaries)
    ↓
    Check prohibited phrases (substring)
    ↓
    Check prohibited claims (substring)
    ↓
    Check restricted terms (context)
    ↓
    Check locale-specific rules
    ↓
Collect Violations
    ↓
Categorize by Severity (error/warning/info)
    ↓
Generate Report
    ↓
If errors: BLOCK campaign
If warnings: Display and proceed
If info: Display and proceed
```

---

## Error Handling Strategy

### 1. Graceful Degradation
- **Guidelines not found** → Continue without (warning)
- **Legal check failure** → Block generation (error)
- **API rate limit** → Exponential backoff retry
- **Image generation failure** → Skip product, continue

### 2. Retry Logic
```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10)
)
async def _call_api():
    ...
```

### 3. Validation
- **Pydantic** - Input validation at data layer
- **Legal Checker** - Content validation at business layer
- **Image Processor** - Runtime validation (dimensions, formats)

---

## Performance Optimizations

### 1. Concurrent Processing
```python
# Process products concurrently
tasks = [
    process_product(product)
    for product in products
]
results = await asyncio.gather(*tasks)
```

### 2. Hero Image Reuse
- Generate once per product
- Reuse across all locales and aspect ratios
- **Savings:** 70-90% reduction in API calls

### 3. HTTP Session Pooling
```python
# Reuse connections
async with aiohttp.ClientSession() as session:
    for request in requests:
        await session.post(...)
```

### 4. Caching
- **Guidelines** - Parsed once, cached in memory
- **Fonts** - Loaded once, reused for all overlays
- **Assets** - Existing assets detected and reused

---

## Security Considerations

### 1. API Key Management
- **Environment variables** - Never hardcode
- **.env file** - Git-ignored
- **Secrets management** - Production should use vault

### 2. Input Validation
- **Pydantic models** - Type and structure validation
- **File path validation** - Prevent directory traversal
- **Prompt sanitization** - Prevent injection attacks

### 3. Legal Compliance
- **Pre-generation checking** - Block prohibited content
- **Audit trail** - Campaign reports track all generations
- **Disclaimer enforcement** - Required notices tracked

---

## Scalability Considerations

### Horizontal Scaling
```
Load Balancer
    ↓
[Pipeline Instance 1] [Pipeline Instance 2] [Pipeline Instance 3]
    ↓
Message Queue (RabbitMQ/SQS)
    ↓
Cloud Storage (S3/Azure Blob)
```

### Vertical Scaling
- **Async operations** - Non-blocking I/O
- **Concurrent processing** - Multiple products in parallel
- **Memory management** - Stream large images
- **Resource pooling** - Connection reuse

---

## Testing Strategy

### 1. Unit Tests
- **Coverage:** ≥80%
- **Focus:** Individual functions, pure logic
- **Mocking:** External API calls

### 2. Integration Tests
- **Coverage:** ≥70%
- **Focus:** Component interactions
- **Test doubles:** Fake services

### 3. End-to-End Tests
- **Coverage:** Critical paths
- **Focus:** Full pipeline execution
- **Environment:** Isolated test data

---

## Deployment Options

### 1. Local Deployment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
./run_cli.sh campaign.json
```

### 2. Docker Deployment
```bash
docker build -t creative-forge-ai .
docker run -v ./output:/app/output creative-forge-ai campaign.json
```

### 3. Cloud Functions (AWS Lambda)
```python
def lambda_handler(event, context):
    brief = event['campaign_brief']
    pipeline = CreativeAutomationPipeline()
    result = await pipeline.process_campaign(brief)
    return result
```

### 4. Kubernetes
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: creative-forge-ai
spec:
  replicas: 3
  selector:
    matchLabels:
      app: creative-forge-ai
  template:
    spec:
      containers:
      - name: pipeline
        image: creative-forge-ai:latest
```

---

## Technology Stack Summary

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Presentation** | Click | CLI framework |
| **Application** | Python 3.11+ | Core logic |
| **Async** | asyncio, aiohttp | Concurrent operations |
| **Data** | Pydantic v2 | Validation |
| **Image** | Pillow (PIL) | Image processing |
| **AI** | Anthropic SDK | Localization |
| **AI** | OpenAI SDK | Image generation |
| **AI** | Google AI SDK | Image generation |
| **Config** | python-dotenv | Environment management |
| **Testing** | pytest | Test framework |

---

## Future Architecture Enhancements

### 1. Microservices
- **Image Service** - Dedicated image generation
- **Localization Service** - Dedicated translation
- **Compliance Service** - Dedicated legal checking
- **Storage Service** - Dedicated asset management

### 2. Event-Driven
- **Message Queue** - Campaign job distribution
- **Event Bus** - Cross-service communication
- **Webhooks** - External integrations

### 3. API Layer
- **REST API** - HTTP endpoints
- **GraphQL** - Flexible querying
- **WebSocket** - Real-time updates

### 4. Observability
- **Logging** - Structured logging (JSON)
- **Metrics** - Prometheus/Grafana
- **Tracing** - OpenTelemetry
- **Monitoring** - Health checks, SLAs

---

## Related Documentation

- **[README.md](README.md)** - Project overview
- **[FEATURES.md](FEATURES.md)** - Feature matrix
- **[API.md](docs/API.md)** - API documentation
- **[PACKAGES.md](docs/PACKAGES.md)** - Code summaries
