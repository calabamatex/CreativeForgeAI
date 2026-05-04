"""OpenAI DALL-E 3 image generation service."""
import aiohttp
import asyncio
from typing import Optional
import structlog
from src.genai.base import ImageGenerationService
from src.models import ComprehensiveBrandGuidelines
from src.config import get_config

logger = structlog.get_logger(__name__)


class OpenAIImageService(ImageGenerationService):
    """Service for generating images using OpenAI DALL-E 3."""
    
    def __init__(self, api_key: Optional[str] = None, max_retries: int = 3):
        config = get_config()
        super().__init__(
            api_key=api_key or config.OPENAI_API_KEY,
            max_retries=max_retries
        )
        self.api_url = "https://api.openai.com/v1/images/generations"
        self.model = "dall-e-3"
    
    async def generate_image(
        self,
        prompt: str,
        size: str = "1024x1024",
        brand_guidelines: Optional[ComprehensiveBrandGuidelines] = None
    ) -> bytes:
        """Generate image using DALL-E 3."""
        
        # Sanitize and enhance prompt with brand guidelines
        if brand_guidelines:
            prompt = self._build_brand_compliant_prompt(prompt, brand_guidelines)
        else:
            prompt = self._sanitize_prompt(prompt)

        logger.debug("openai.prompt", prompt=prompt)

        # DALL-E 3 accepts: 1024x1024, 1024x1792, 1792x1024
        dalle_size = self._convert_size_format(size)
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "n": 1,
            "size": dalle_size,
            "quality": "hd",  # Use HD quality
            "style": "natural"  # Natural vs vivid
        }
        
        for attempt in range(self.max_retries):
            try:
                session = await self._get_session()
                async with session.post(
                    self.api_url,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        image_url = data["data"][0]["url"]
                        async with session.get(image_url) as img_response:
                            if img_response.status == 200:
                                return await img_response.read()
                            raise Exception(f"Image download failed: {img_response.status}")
                    elif response.status == 429:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    else:
                        error_text = await response.text()
                        logger.warning("openai.api_error", status=response.status, error=error_text)
                        if attempt < self.max_retries - 1:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        raise Exception(f"OpenAI API error: {response.status}")
            except asyncio.TimeoutError:
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise
        raise Exception("Max retries exceeded for OpenAI API")
    
    def _convert_size_format(self, size: str) -> str:
        """Convert generic size to DALL-E 3 format."""
        # Map common sizes to DALL-E 3 supported sizes
        size_map = {
            "1024x1024": "1024x1024",
            "2048x2048": "1024x1024",  # Downscale to supported
            "1080x1920": "1024x1792",  # Portrait
            "1920x1080": "1792x1024",  # Landscape
            "1024x768": "1024x1024",   # Square
        }
        return size_map.get(size, "1024x1024")
    
    def get_backend_name(self) -> str:
        """Return backend name."""
        return "OpenAI DALL-E 3"
    
    def validate_config(self) -> tuple[bool, list[str]]:
        """Validate OpenAI configuration."""
        errors = []
        if not self.api_key:
            errors.append("OPENAI_API_KEY is required")
        return len(errors) == 0, errors
