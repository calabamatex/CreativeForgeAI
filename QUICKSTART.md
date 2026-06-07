# Quick Start Guide

## 🚀 Get Running in 5 Minutes

Get up and running with the Creative Automation Pipeline in 5 minutes.

### Prerequisites

- **Python 3.11+** installed
- **API Keys** (at least Claude + one image backend)
- **Git** installed

### Step 1: Clone Repository

```bash
git clone https://github.com/calabamatex/CreativeForgeAI.git
cd CreativeForgeAI
```

### Step 2: Create Virtual Environment

```bash
# Create venv
python3 -m venv venv

# Activate (macOS/Linux)
source venv/bin/activate

# Activate (Windows)
venv\Scripts\activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Configure API Keys

```bash
cp .env.example .env
# Edit .env and add your API keys:
# - FIREFLY_API_KEY
# - FIREFLY_CLIENT_ID
# - ANTHROPIC_API_KEY
```

You need Claude (for localization) plus at least ONE image backend
(OpenAI, Google Gemini, or Adobe Firefly).

### Step 5: Validate Setup

```bash
python -m src.cli validate-config
```

### Step 6: Run Example Campaign

```bash
python -m src.cli process --brief examples/campaign_brief.json --verbose
```

## 📊 What to Expect

The pipeline will:
1. Load campaign brief with 2 products
2. Parse brand guidelines (colors, fonts, style)
3. Parse localization rules (3 locales: en-US, es-MX, fr-CA)
4. Generate hero images using the configured image backend
5. Create 3 aspect ratios per product per locale
6. Apply text overlays with brand compliance
7. Save 18 total assets (2 products × 3 locales × 3 ratios)

**Expected Output:**
```
output/
└── SUMMER2026/
    ├── en-US/
    │   ├── HEADPHONES-001/
    │   │   ├── 1x1/HEADPHONES-001_1x1_en-US.png
    │   │   ├── 9x16/HEADPHONES-001_9x16_en-US.png
    │   │   └── 16x9/HEADPHONES-001_16x9_en-US.png
    │   └── SMARTWATCH-002/
    ├── es-MX/
    └── fr-CA/
    └── campaign_report.json
```

## 🎥 For Demo/Presentation

1. **Show Configuration:**
   ```bash
   python -m src.cli validate-config
   ```

2. **Show Examples:**
   ```bash
   python -m src.cli list-examples
   ```

3. **Run Campaign (Verbose):**
   ```bash
   python -m src.cli process --brief examples/campaign_brief.json --verbose
   ```

4. **Show Results:**
   - Navigate to `output/SUMMER2026/`
   - Show generated images
   - Open `campaign_report.json`

## 🎯 Customize Your Campaign

Edit `examples/campaign_brief.json`:

```json
{
  "campaign_id": "MY_CAMPAIGN",
  "campaign_name": "My First Campaign",
  "products": [
    {
      "product_name": "My Product",
      "generation_prompt": "professional photo of my product"
    }
  ]
}
```

### Add Brand Guidelines

```bash
# Use example
cp examples/guidelines/brand_guidelines.yaml my_brand.yaml

# Edit colors, fonts, logo settings
nano my_brand.yaml

# Reference in campaign
"brand_guidelines_file": "my_brand.yaml"
```

### Enable Legal Compliance

```json
{
  "legal_compliance_file": "examples/guidelines/legal_compliance_general.yaml"
}
```

### Try Different Backends

```bash
# Use default backend
./run_cli.sh examples/campaign_brief.json

# Specify backend as second argument:

# Adobe Firefly (commercial-safe, high quality)
./run_cli.sh examples/campaign_brief.json firefly

# OpenAI DALL-E 3 (creative, high quality)
./run_cli.sh examples/campaign_brief.json openai

# Google Gemini Imagen 4 (fast, high quality)
./run_cli.sh examples/campaign_brief.json gemini

# Show all options
./run_cli.sh --help
```

## 🧪 Run Tests

```bash
# Run all tests
pytest

# With coverage
pytest --cov=src --cov-report=html

# Open coverage report
open htmlcov/index.html
```

## 📝 Key Files to Review

- **README.md** - Complete documentation
- **src/pipeline.py** - Main orchestrator logic
- **src/genai/claude.py** - AI extraction & localization
- **src/genai/firefly.py** - Image generation
- **examples/campaign_brief.json** - Example input
- **examples/guidelines/** - Brand & localization rules

## ⏱️ Performance Target

- **Target:** <3 minutes for 2-product, 2-locale campaign
- **Typical:** 2-2.5 minutes
- **Output:** 18 high-quality campaign assets

## 🎯 Next Steps

1. Add your real API keys to `.env`
2. Run the example campaign
3. Review generated assets
4. Customize `campaign_brief.json` for your use case
5. Add your own brand guidelines
6. Scale to more products/locales

## 💡 Tips

- Start with `--dry-run` to validate without processing
- Use `--verbose` to see detailed progress
- Check `campaign_report.json` for complete metrics
- Each run creates timestamped output directory
- Reuses hero images across locales for efficiency

## 🛠️ Common Issues

### "API key not found"
**Solution:** Check `.env` file exists and has correct keys

### "Module not found"
**Solution:** Ensure venv is activated: `source venv/bin/activate`

### "Rate limit exceeded"
**Solution:** Wait 60 seconds, system will auto-retry

### "Image generation failed"
**Solution:** Check prompt is valid, verify API key permissions

## 🆘 Getting Help

- **Documentation:** [Full Docs](docs/)
- **Issues:** [GitHub Issues](https://github.com/calabamatex/CreativeForgeAI/issues)
- **Examples:** `examples/campaigns/` directory

---

**Need Help?** Check README.md for troubleshooting and detailed documentation.
