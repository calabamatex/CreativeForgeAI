# Quick Start Guide

Get up and running with Creative Automation Pipeline in 5 minutes.

---

## Prerequisites

- **Python 3.11+** installed
- **API Keys** (at least Claude + one image backend)
- **Git** installed

---

## Step 1: Clone Repository

```bash
git clone https://github.com/calabamatex/CreativeForgeAI.git
cd CreativeForgeAI
```

---

## Step 2: Create Virtual Environment

```bash
# Create venv
python3 -m venv venv

# Activate (macOS/Linux)
source venv/bin/activate

# Activate (Windows)
venv\Scripts\activate
```

---

## Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Step 4: Configure API Keys

Create `.env` file:

```bash
# Required: Claude for localization
ANTHROPIC_API_KEY=sk-ant-your-key-here

# Required: At least ONE image backend

# Option 1: OpenAI (recommended for getting started)
OPENAI_API_KEY=sk-your-key-here

# Option 2: Google Gemini
GOOGLE_API_KEY=your-google-key

# Option 3: Adobe Firefly
ADOBE_CLIENT_ID=your-client-id
ADOBE_CLIENT_SECRET=your-client-secret
```

---

## Step 5: Run Example Campaign

```bash
./run_cli.sh examples/campaign_brief.json
```

**Output:**
```
🚀 Processing Campaign: Summer Tech Collection 2026
Campaign ID: SUMMER2026
Image Backend: OpenAI DALL-E 3
Products: 2
Target Locales: en-US, es-MX

🎨 Generating assets for 2 products...
📦 Processing product: Premium Wireless Headphones
  🎨 Generating hero image with OpenAI DALL-E 3...
  ✓ Hero image generated
  🌍 Processing locale: en-US
    📐 Generating 1:1 variation...
    ✓ Saved: output/SUMMER2026/en-US/HEADPHONES-001/1x1/...
...

✅ Campaign processing complete!
   Total assets generated: 12
   Processing time: 45.2 seconds
   Success rate: 100.0%
```

---

## Step 6: View Generated Assets

```bash
# View output directory
ls -R output/

# Example structure:
output/
├── HEADPHONES-001/
│   └── SUMMER2026/
│       ├── hero/
│       │   └── HEADPHONES-001_hero.png
│       ├── en-US/
│       │   ├── 1x1/HEADPHONES-001_1x1_en-US.png
│       │   ├── 16x9/HEADPHONES-001_16x9_en-US.png
│       │   └── 9x16/HEADPHONES-001_9x16_en-US.png
│       ├── es-MX/
│       │   └── ...
│       └── HEADPHONES-001_campaign_report.json
└── SMARTWATCH-002/
    └── SUMMER2026/
        ├── hero/
        │   └── SMARTWATCH-002_hero.png
        ├── en-US/
        │   └── ...
        └── SMARTWATCH-002_campaign_report.json
```

**New Structure Benefits:**
- Each product has its own folder
- Easy to share all campaigns for a specific product
- Per-product campaign reports
- Clean organization for multi-product campaigns

---

## Next Steps

### Customize Your Campaign

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
# Use default backend (gemini)
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

---

## Common Issues

### "API key not found"
**Solution:** Check `.env` file exists and has correct keys

### "Module not found"
**Solution:** Ensure venv is activated: `source venv/bin/activate`

### "Rate limit exceeded"
**Solution:** Wait 60 seconds, system will auto-retry

### "Image generation failed"
**Solution:** Check prompt is valid, verify API key permissions

---

## Getting Help

- **Documentation:** [Full Docs](docs/)
- **Issues:** [GitHub Issues](https://github.com/calabamatex/CreativeForgeAI/issues)
- **Examples:** `examples/campaigns/` directory
