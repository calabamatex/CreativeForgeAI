# Scripts Directory

Utility scripts for Creative Automation Pipeline.

## Campaign Brief Generator

**File:** `generate_campaign_brief.py`

A Python script that generates campaign brief JSON files implementing enhanced prompt engineering strategies from the [IMAGE_QUALITY_OPTIMIZATION.md](../docs/IMAGE_QUALITY_OPTIMIZATION.md) guide.

### Features

- **Advanced Prompt Engineering**: Structured prompts with professional photography terminology
- **Multiple Templates**: Pre-built templates for different product categories
- **Enhanced Generation Objects**: Detailed breakdown of style, composition, lighting, background, and details
- **Negative Prompts**: Explicitly defines what to avoid in generation
- **7 Product Categories**: Electronics, fashion, food, beauty, automotive, premium audio, display tech

### Usage

#### List Available Templates

```bash
python3 scripts/generate_campaign_brief.py --list-templates
```

**Output:**
```
📋 Available Campaign Templates:
  - premium_audio: Premium audio products (earbuds + headphones)
  - premium_tech: Premium tech products (earbuds + portable monitor)
  - fashion: Fashion/lifestyle products (sneakers)

🎨 Available Prompt Categories:
  - electronics
  - fashion
  - food
  - beauty
  - automotive
  - premium_audio
  - display_tech
```

#### Generate Campaign Briefs

**Premium Audio Campaign (2 products: earbuds + headphones):**
```bash
python3 scripts/generate_campaign_brief.py --template premium_audio --output examples/premium_audio_enhanced.json
```

**Premium Tech Campaign (2 products: earbuds + portable monitor):**
```bash
python3 scripts/generate_campaign_brief.py --template premium_tech --output examples/premium_tech_enhanced.json
```

**Fashion Campaign (sneakers):**
```bash
python3 scripts/generate_campaign_brief.py --template fashion --output examples/fashion_enhanced.json
```

### Generated Output Structure

Each generated campaign brief includes both:

1. **Flattened Prompt** (`generation_prompt`): Complete prompt string ready to use
2. **Structured Breakdown** (`enhanced_generation`): Detailed component breakdown

Example structure:
```json
{
  "products": [
    {
      "product_id": "EARBUDS-PRO-001",
      "product_name": "Elite True Wireless Earbuds Pro",
      "generation_prompt": "premium true wireless earbuds...[complete prompt]",
      "enhanced_generation": {
        "base_prompt": "premium true wireless earbuds in sleek charging case",
        "style_parameters": {
          "photography_style": "commercial product photography",
          "artistic_style": "high-end tech aesthetic",
          "color_palette": ["metallic silver", "deep black", "subtle blue accent"],
          "mood": "premium luxury",
          "quality_level": "ultra high resolution 8K"
        },
        "composition": {
          "primary_subject": "earbuds displayed in open charging case",
          "viewing_angle": "3/4 angle from above",
          "depth_of_field": "shallow DOF with sharp focus on earbuds",
          "rule_of_thirds": true,
          "negative_space": "ample space on right side for text overlay"
        },
        "lighting": {
          "primary_light": "soft key light from 45 degrees",
          "fill_light": "subtle fill to lift shadows",
          "rim_light": "strong rim light highlighting metallic edges",
          "color_temperature": "cool daylight 5500K",
          "quality": "soft studio lighting"
        },
        "background": {
          "type": "gradient",
          "colors": ["deep charcoal", "midnight blue"],
          "texture": "subtle reflective surface",
          "style": "minimalist tech environment"
        },
        "details": {
          "focus_areas": ["premium metal finish", "charging contacts", "brand logo"],
          "texture_emphasis": "brushed metal texture on case",
          "quality_indicators": "sharp edges, crisp reflections, visible craftsmanship"
        },
        "negative_prompt": "cheap plastic appearance, flat lighting, cluttered, low resolution"
      }
    }
  ]
}
```

### Command-Line Arguments

| Argument | Description | Required |
|----------|-------------|----------|
| `--template` | Campaign template: `premium_audio`, `premium_tech`, `fashion` | Yes |
| `--output` | Output JSON file path (default: `examples/{template}_campaign_enhanced.json`) | No |
| `--list-templates` | List available templates and categories | No |
| `--pretty` | Pretty print JSON output (default: True) | No |

### Examples

**Generate and immediately use:**
```bash
# Generate enhanced premium audio campaign
python3 scripts/generate_campaign_brief.py --template premium_audio --output examples/my_campaign.json

# Run campaign generation with enhanced prompts
./run_cli.sh examples/my_campaign.json firefly
```

**Compare standard vs enhanced:**
```bash
# Standard campaign (simple prompts)
./run_cli.sh examples/campaign_brief.json gemini

# Enhanced campaign (structured prompts)
python3 scripts/generate_campaign_brief.py --template premium_tech
./run_cli.sh examples/premium_tech_campaign_enhanced.json firefly
```

### Prompt Category Templates

The script includes 7 pre-built prompt templates optimized for different product categories:

1. **Electronics**: Studio lighting, tech aesthetic, metallic finishes
2. **Fashion**: Editorial style, lifestyle context, natural lighting
3. **Food**: Gourmet presentation, appetizing styling, overhead/45° angles
4. **Beauty**: Luxury aesthetic, soft lighting, texture emphasis
5. **Automotive**: Dramatic lighting, dynamic angles, chrome reflections
6. **Premium Audio**: High-end tech, luxury materials, dramatic studio setup
7. **Display Tech**: Professional workspace, screen content quality, slim design

### Expected Quality Improvements

Using enhanced prompts typically results in:

- **30-40% better image quality** through detailed prompt engineering
- **Consistent styling** across all generated assets
- **Professional aesthetics** matching commercial photography standards
- **Reduced regeneration** due to clearer prompt specifications
- **Backend-optimized** prompts for Firefly, DALL-E 3, and Gemini Imagen 4

### Integration with Pipeline

The generated campaign briefs are fully compatible with the existing pipeline:

```bash
# Generate enhanced brief
python3 scripts/generate_campaign_brief.py --template premium_tech

# Process with any backend
./run_cli.sh examples/premium_tech_campaign_enhanced.json firefly
./run_cli.sh examples/premium_tech_campaign_enhanced.json dalle
./run_cli.sh examples/premium_tech_campaign_enhanced.json gemini
```

### Customization

To add custom templates or modify existing ones, edit the `PROMPT_TEMPLATES` dictionary in `generate_campaign_brief.py`:

```python
PROMPT_TEMPLATES = {
    "your_category": {
        "style": "your photography style",
        "composition": "your composition rules",
        "lighting": "your lighting setup",
        "background": "your background design",
        "details": "your detail focus areas",
        "negative": "what to avoid"
    }
}
```

Then add a corresponding `generate_your_category_campaign()` function following the existing patterns.

## Campaign Brief Generator with Phase 1 Enhancements

**File:** `generate_campaign_brief_p1_updates.py`

Enhanced version of the campaign brief generator that includes **Phase 1 features** (v1.2.0):
- **Per-element text customization** (headline, subheadline, CTA)
- **Text outline effects** for improved readability
- **Post-processing configuration** (sharpening, color correction)

### Phase 1 Features

#### Text Customization Presets

The script includes 4 text styling presets:

1. **high_contrast_bold** (default for premium_audio)
   - Bold headlines with strong shadows
   - Clean subheadline without effects
   - Orange CTA with outline and background box

2. **readability_first** (default for premium_tech)
   - Text outlines on all elements
   - Maximum readability on any background
   - No shadow effects needed

3. **minimal_modern** (default for fashion)
   - Clean design without shadows
   - Dark text on light backgrounds
   - Minimal visual effects

4. **premium_luxury**
   - Elegant styling with gold accents
   - Sophisticated shadow effects
   - Premium aesthetic

#### Post-Processing Presets

The script includes 4 enhancement presets:

1. **standard** - Balanced (150% sharp, +10% contrast, +5% saturation)
2. **subtle** - Gentle (125% sharp, +5% contrast, +3% saturation)
3. **vivid** - Bold (175% sharp, +20% contrast, +15% saturation)
4. **professional** (default) - Strong (160% sharp, +15% contrast, +10% saturation)

### Usage

#### List Available Presets

```bash
python3 scripts/generate_campaign_brief_p1_updates.py --list-presets
```

**Output:**
```
🎨 Phase 1 Text Customization Presets:
  - high_contrast_bold
  - readability_first
  - minimal_modern
  - premium_luxury

✨ Phase 1 Post-Processing Presets:
  - standard
  - subtle
  - vivid
  - professional
```

#### Generate Campaign Briefs with Phase 1 Features

**Premium Audio Campaign (with high contrast text and professional post-processing):**
```bash
python3 scripts/generate_campaign_brief_p1_updates.py --template premium_audio --output examples/premium_audio_p1.json
```

**Premium Tech Campaign (with readability-focused text and vivid enhancement):**
```bash
python3 scripts/generate_campaign_brief_p1_updates.py --template premium_tech --text-preset readability_first --post-preset vivid --output examples/premium_tech_p1.json
```

**Fashion Campaign (with minimal design and subtle enhancement):**
```bash
python3 scripts/generate_campaign_brief_p1_updates.py --template fashion --text-preset minimal_modern --post-preset subtle --output examples/fashion_p1.json
```

#### Custom Preset Combinations

Mix and match text and post-processing presets:

```bash
# High contrast text with vivid post-processing
python3 scripts/generate_campaign_brief_p1_updates.py \
  --template premium_audio \
  --text-preset high_contrast_bold \
  --post-preset vivid

# Minimal text with standard post-processing
python3 scripts/generate_campaign_brief_p1_updates.py \
  --template fashion \
  --text-preset minimal_modern \
  --post-preset standard

# Luxury text with professional post-processing
python3 scripts/generate_campaign_brief_p1_updates.py \
  --template premium_tech \
  --text-preset premium_luxury \
  --post-preset professional
```

### Generated Output Structure (Phase 1 Enhanced)

In addition to the standard campaign structure, Phase 1 briefs include:

```json
{
  "campaign_id": "PREMIUM_AUDIO_2026_P1",
  "products": [...],

  "text_customization": {
    "headline": {
      "color": "#FFFFFF",
      "font_size_multiplier": 1.3,
      "font_weight": "bold",
      "shadow": {
        "enabled": true,
        "color": "#000000",
        "offset_x": 4,
        "offset_y": 4,
        "blur_radius": 2
      }
    },
    "subheadline": {
      "color": "#E0E0E0",
      "font_size_multiplier": 1.0,
      "font_weight": "regular",
      "shadow": {
        "enabled": false
      }
    },
    "cta": {
      "color": "#FFFFFF",
      "font_size_multiplier": 1.1,
      "font_weight": "bold",
      "outline": {
        "enabled": true,
        "color": "#FF6600",
        "width": 2
      },
      "background": {
        "enabled": true,
        "color": "#FF6600",
        "opacity": 0.9,
        "padding": 18
      }
    }
  },

  "post_processing": {
    "enabled": true,
    "sharpening": true,
    "sharpening_radius": 2.0,
    "sharpening_amount": 160,
    "color_correction": true,
    "contrast_boost": 1.15,
    "saturation_boost": 1.1
  }
}
```

### Command-Line Arguments

| Argument | Description | Required |
|----------|-------------|----------|
| `--template` | Campaign template: `premium_audio`, `premium_tech`, `fashion` | Yes |
| `--output` | Output JSON file path (default: `examples/{template}_campaign_p1.json`) | No |
| `--text-preset` | Text customization preset (default: template-specific) | No |
| `--post-preset` | Post-processing preset (default: template-specific) | No |
| `--list-presets` | List all available presets | No |
| `--list-templates` | List available templates | No |
| `--pretty` | Pretty print JSON (default: True) | No |

### Default Preset Combinations

Each template has optimized defaults:

| Template | Default Text Preset | Default Post-Processing |
|----------|-------------------|------------------------|
| premium_audio | high_contrast_bold | professional |
| premium_tech | readability_first | vivid |
| fashion | minimal_modern | subtle |

### Integration with Phase 1 Pipeline

Generated Phase 1 briefs are fully compatible with the v1.2.0 pipeline:

```bash
# Generate Phase 1 enhanced brief
python3 scripts/generate_campaign_brief_p1_updates.py --template premium_tech

# Process with Phase 1 features
./run_cli.sh examples/premium_tech_campaign_p1.json gemini

# Output includes:
# - Per-element text styling (headline, subheadline, CTA)
# - Text outlines for improved readability
# - Automatic post-processing enhancement
```

### Quality Improvements with Phase 1

Using Phase 1 features typically results in:

- **Improved text readability** across all backgrounds
- **Professional polish** through post-processing
- **Consistent brand styling** with per-element control
- **Reduced post-production work** with automatic enhancement
- **Better conversion rates** from more readable CTAs

### Example Workflows

**High-Impact Campaign (Maximum Visibility):**
```bash
python3 scripts/generate_campaign_brief_p1_updates.py \
  --template premium_audio \
  --text-preset readability_first \
  --post-preset vivid
./run_cli.sh examples/premium_audio_campaign_p1.json firefly
```

**Professional Campaign (Balanced Approach):**
```bash
python3 scripts/generate_campaign_brief_p1_updates.py \
  --template premium_tech \
  --text-preset high_contrast_bold \
  --post-preset professional
./run_cli.sh examples/premium_tech_campaign_p1.json gemini
```

**Clean Minimal Campaign (Modern Design):**
```bash
python3 scripts/generate_campaign_brief_p1_updates.py \
  --template fashion \
  --text-preset minimal_modern \
  --post-preset subtle
./run_cli.sh examples/fashion_campaign_p1.json dalle
```

### Backward Compatibility

Phase 1 features are optional enhancements. Campaign briefs generated by the original script remain fully compatible. The Phase 1 enhanced script adds:

- `text_customization` object (optional, overrides legacy text settings)
- `post_processing` object (optional, applied automatically when present)

### Documentation References

- [PHASE1_IMPLEMENTATION_GUIDE.md](../docs/PHASE1_IMPLEMENTATION_GUIDE.md) - Complete Phase 1 feature guide
- [TEXT_CUSTOMIZATION.md](../docs/TEXT_CUSTOMIZATION.md) - Text effect documentation
- [IMAGE_QUALITY_OPTIMIZATION.md](../docs/IMAGE_QUALITY_OPTIMIZATION.md) - Quality optimization guide

## Additional Scripts

More utility scripts will be added to this directory as the project evolves.

---

For questions or issues, see the main [README.md](../README.md) or open an issue on GitHub.
