# Multi-Backend Image Generation Guide

The Creative Automation Pipeline supports multiple GenAI image generation backends, allowing you to choose the best provider for your specific needs.

## Supported Backends

### 1. Adobe Firefly (Default)
- **Model**: Firefly Image 3 Model
- **Best For**: Brand-safe, commercially licensed imagery
- **Key Features**:
  - Commercial-safe training data
  - Advanced brand compliance
  - Multiple aspect ratios
  - Style references
  - Content credentials
- **Requirements**: Firefly API Key + Client ID + OAuth IMS access token (see Adobe Firefly Services docs)
- **Cost**: Pay-per-use; pricing per Adobe Firefly Services billing

### 2. OpenAI DALL-E 3
- **Model**: DALL-E 3
- **Best For**: High-quality, creative imagery
- **Key Features**:
  - Superior prompt understanding
  - HD quality (1024x1024, 1024x1792, 1792x1024)
  - Natural language prompts
  - Detailed control
- **Requirements**: OpenAI API Key
- **Cost**: $0.040 per image (1024x1024), $0.080 per HD image

### 3. Google Gemini Imagen 3
- **Model**: Imagen 3.0
- **Best For**: Photorealistic imagery
- **Key Features**:
  - Photorealistic quality
  - Text rendering support
  - Negative prompts
  - Aspect ratio control
  - Base64 image response
- **Requirements**: Google Cloud API Key
- **Cost**: Based on Google Cloud pricing

### 4. Claude (Anthropic) - Placeholder
- **Status**: Not yet available
- **Purpose**: Future compatibility when Anthropic releases image generation
- **Current Role**: Text processing (guideline extraction, localization)
- **Note**: Will raise `NotImplementedError` if selected

## Configuration

### Environment Variables

Create a `.env` file with your API keys:

```bash
# Adobe Firefly (Default)
FIREFLY_API_KEY=your_firefly_api_key_here
FIREFLY_CLIENT_ID=your_firefly_client_id_here

# OpenAI DALL-E 3
OPENAI_API_KEY=sk-your_openai_key_here

# Google Gemini Imagen
GEMINI_API_KEY=your_gemini_api_key_here

# Default backend (if not specified in brief or CLI)
DEFAULT_IMAGE_BACKEND=firefly
```

### Validate Configuration

Check which backends are configured:

```bash
python -m src.cli validate-config
```

Output:
```
✅ Configuration is valid

📡 Image Generation Backends:
  Adobe Firefly: ✓
  OpenAI DALL-E: ✓
  Google Gemini: ✓

  Available: firefly, openai, gemini
  Default: firefly

🔤 Text Processing:
  Claude API: ✓
```

## Usage

### Method 1: Campaign Brief (Recommended)

Specify backend in your campaign brief JSON:

```json
{
  "campaign_id": "SUMMER2026",
  "campaign_name": "Summer Collection",
  "image_generation_backend": "openai",
  "products": [...]
}
```

Valid values: `firefly`, `openai`, `dalle`, `gemini`, `imagen`

### Method 2: CLI Override

Override the backend at runtime:

```bash
# Use OpenAI instead of brief's backend
python -m src.cli process --brief examples/campaign_brief.json --backend openai

# Use Gemini
python -m src.cli process --brief examples/campaign_brief.json --backend gemini

# Use Firefly (explicit)
python -m src.cli process --brief examples/campaign_brief.json --backend firefly
```

### Method 3: Programmatic Usage

```python
from src.pipeline import CreativeAutomationPipeline
from src.models import CampaignBrief

# Create pipeline with specific backend
pipeline = CreativeAutomationPipeline(image_backend="gemini")

# Load campaign brief
with open("campaign_brief.json") as f:
    brief = CampaignBrief(**json.load(f))

# Process (uses Gemini regardless of brief setting)
output = await pipeline.process_campaign(brief)
```

## Backend Selection Priority

The system follows this priority order:

1. **CLI Flag** (`--backend`) - Highest priority
2. **Campaign Brief** (`image_generation_backend` field)
3. **Environment Variable** (`DEFAULT_IMAGE_BACKEND`)
4. **System Default** (`firefly`)

Example:
```bash
# Brief says "gemini", CLI says "openai"
# Result: Uses OpenAI (CLI wins)
python -m src.cli process --brief brief.json --backend openai
```

## Backend Comparison

| Feature | Firefly | DALL-E 3 | Gemini Imagen 3 |
|---------|---------|----------|-----------------|
| **Image Quality** | Excellent | Excellent | Photorealistic |
| **Prompt Understanding** | Very Good | Excellent | Very Good |
| **Commercial Safety** | ✅ Guaranteed | ⚠️ Check terms | ⚠️ Check terms |
| **Brand Compliance** | Native support | Via prompts | Via prompts |
| **Aspect Ratios** | All | 3 sizes | Flexible |
| **Text Rendering** | Good | Good | Excellent |
| **Speed** | Fast | Fast | Fast |
| **Cost** | Pay-per-use | $0.04-0.08/img | Variable |
| **Content Credentials** | ✅ Yes | ❌ No | ❌ No |

## Best Practices

### Choosing a Backend

**Use Firefly when:**
- You need commercially-safe, licensed imagery
- Brand compliance is critical
- You're working with regulated industries
- Content credentials are required

**Use DALL-E 3 when:**
- You need maximum creative control
- Prompt understanding is critical
- You want HD quality outputs
- Cost is not a primary concern

**Use Gemini when:**
- You need photorealistic imagery
- Text rendering in images is important
- You're already using Google Cloud
- You want negative prompt control

### Multi-Backend Strategy

Consider using different backends for different purposes:

```json
{
  "products": [
    {
      "product_id": "hero-image",
      "generation_backend": "firefly",
      "note": "Brand-safe hero image"
    },
    {
      "product_id": "lifestyle-shot",
      "generation_backend": "gemini",
      "note": "Photorealistic lifestyle imagery"
    },
    {
      "product_id": "creative-concept",
      "generation_backend": "openai",
      "note": "Creative interpretation"
    }
  ]
}
```

## Troubleshooting

### Backend Not Available

**Error**: `Backend 'openai' is not available`

**Cause**: Missing API key in environment

**Fix**:
```bash
# Add to .env file
OPENAI_API_KEY=sk-your_key_here

# Verify
python -m src.cli validate-config
```

### Invalid Backend Name

**Error**: `Invalid image generation backend: xyz`

**Valid backends**: `firefly`, `openai`, `dall-e`, `dalle`, `gemini`, `imagen`, `claude`

### API Key Errors

**Firefly**: Check both `FIREFLY_API_KEY` and `FIREFLY_CLIENT_ID` are set

**OpenAI**: Verify key starts with `sk-` and has sufficient credits

**Gemini**: Ensure Google Cloud project is configured correctly

### Rate Limits

All backends implement retry logic with exponential backoff:

```python
# Configured in each service
max_retries: int = 3  # Default
retry_delay: float = 1.0  # Initial delay in seconds
```

## Advanced: Custom Backends

### Creating a Custom Backend

1. Extend the base class:

```python
from src.genai.base import ImageGenerationService
from typing import Optional
from src.models import ComprehensiveBrandGuidelines

class MyCustomService(ImageGenerationService):
    def __init__(self, api_key: str, max_retries: int = 3):
        super().__init__(api_key=api_key, max_retries=max_retries)
        self.api_url = "https://api.example.com/generate"

    async def generate_image(
        self,
        prompt: str,
        size: str = "1024x1024",
        brand_guidelines: Optional[ComprehensiveBrandGuidelines] = None
    ) -> bytes:
        # Build brand-compliant prompt
        enhanced_prompt = self._build_brand_compliant_prompt(
            prompt, brand_guidelines
        )

        # Call your API
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.api_url,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"prompt": enhanced_prompt, "size": size}
            ) as response:
                return await response.read()

    def get_backend_name(self) -> str:
        return "My Custom Backend"
```

2. Register in factory:

```python
# src/genai/factory.py
from src.genai.my_custom import MyCustomService

class ImageGenerationFactory:
    BACKENDS = {
        # ... existing backends ...
        "custom": MyCustomService,
    }
```

3. Use it:

```bash
DEFAULT_IMAGE_BACKEND=custom
CUSTOM_API_KEY=your_key_here
```

## API Reference

### Base Class Interface

All backends must implement:

```python
class ImageGenerationService(ABC):
    """Abstract base class for image generation backends."""

    @abstractmethod
    async def generate_image(
        self,
        prompt: str,
        size: str = "1024x1024",
        brand_guidelines: Optional[ComprehensiveBrandGuidelines] = None
    ) -> bytes:
        """
        Generate an image from a text prompt.

        Args:
            prompt: Text description of desired image
            size: Image size (format varies by backend)
            brand_guidelines: Optional brand compliance guidelines

        Returns:
            Image data as bytes (PNG/JPG)

        Raises:
            Exception: If generation fails
        """
        pass

    def get_backend_name(self) -> str:
        """Return human-readable backend name."""
        pass

    def _build_brand_compliant_prompt(
        self,
        base_prompt: str,
        guidelines: Optional[ComprehensiveBrandGuidelines]
    ) -> str:
        """Enhance prompt with brand guidelines."""
        pass
```

## Performance Comparison

Typical generation times (approximate):

| Backend | Average Time | Max Resolution | Concurrent Limit |
|---------|--------------|----------------|------------------|
| Firefly | 3-5s | 2048x2048 | Varies by plan |
| DALL-E 3 | 10-15s | 1792x1024 | 5/min (tier 1) |
| Gemini | 5-8s | Flexible | Varies by quota |

## Future Roadmap

Planned backend additions:

- **Claude Image Generation**: When Anthropic releases image capabilities
- **Midjourney API**: If/when public API is available
- **Stable Diffusion**: Self-hosted option
- **Azure AI**: Microsoft's image generation services

## Support

For backend-specific issues:

- **Firefly**: [Adobe Developer Console](https://developer.adobe.com)
- **OpenAI**: [OpenAI Platform](https://platform.openai.com)
- **Gemini**: [Google Cloud Console](https://console.cloud.google.com)

For pipeline issues: [GitHub Issues](https://github.com/your-org/creative-automation-pipeline/issues)
