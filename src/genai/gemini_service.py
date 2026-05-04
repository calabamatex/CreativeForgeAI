"""Google Gemini Imagen service using Imagen 4."""
import aiohttp
import asyncio
import base64
import json
from typing import Optional
import structlog
from src.genai.base import ImageGenerationService
from src.models import ComprehensiveBrandGuidelines
from src.config import get_config

logger = structlog.get_logger(__name__)


class GeminiImageService(ImageGenerationService):
    """Service for generating images using Google Gemini Imagen 4."""

    def __init__(self, api_key: Optional[str] = None, max_retries: int = 3):
        config = get_config()
        super().__init__(
            api_key=api_key or config.GEMINI_API_KEY,
            max_retries=max_retries
        )
        # Using Imagen 4 via Google AI Studio API (latest version as of 2025/2026)
        # Note: This uses the generativelanguage API with API key authentication
        # Available models: imagen-4.0-generate-001 (standard), imagen-4.0-fast-generate-001, imagen-4.0-ultra-generate-001
        self.api_url = "https://generativelanguage.googleapis.com/v1beta/models/imagen-4.0-generate-001:predict"
        self.model = "imagen-4.0-generate-001"

    async def generate_image(
        self,
        prompt: str,
        size: str = "1024x1024",
        brand_guidelines: Optional[ComprehensiveBrandGuidelines] = None
    ) -> bytes:
        """Generate image using Gemini Imagen 4."""

        # Sanitize and enhance prompt with brand guidelines
        if brand_guidelines:
            prompt = self._build_brand_compliant_prompt(prompt, brand_guidelines)
        else:
            prompt = self._sanitize_prompt(prompt)

        logger.debug("gemini.prompt", prompt=prompt)

        # Parse size
        width, height = map(int, size.split('x'))

        # Google AI Studio API key goes in x-goog-api-key header
        headers = {
            "x-goog-api-key": self.api_key,
            "Content-Type": "application/json"
        }

        # Google AI Studio Imagen API format (predict endpoint)
        payload = {
            "instances": [
                {
                    "prompt": prompt
                }
            ],
            "parameters": {
                "sampleCount": 1,
                "aspectRatio": self._get_aspect_ratio(width, height)
            }
        }

        # Add negative prompt if available
        negative_prompt = self._get_negative_prompt(brand_guidelines)
        if negative_prompt:
            payload["parameters"]["negativePrompt"] = negative_prompt

        # Add person generation setting
        payload["parameters"]["personGeneration"] = "allow_adult"

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
                        if "predictions" in data:
                            image_b64 = data["predictions"][0]["bytesBase64Encoded"]
                        else:
                            logger.error("gemini.unexpected_response", keys=list(data.keys()))
                            raise Exception("Gemini API returned an unexpected response format")
                        return base64.b64decode(image_b64)
                    elif response.status == 429:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    else:
                        error_text = await response.text()
                        logger.warning("gemini.api_error", status=response.status, error=error_text)
                        if attempt < self.max_retries - 1:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        raise Exception(f"Gemini API error: {response.status}")
            except asyncio.TimeoutError:
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise
        raise Exception("Max retries exceeded for Gemini API")
    
    def _get_aspect_ratio(self, width: int, height: int) -> str:
        """Determine aspect ratio for Imagen."""
        ratio = width / height
        
        if abs(ratio - 1.0) < 0.1:
            return "1:1"
        elif abs(ratio - 16/9) < 0.1:
            return "16:9"
        elif abs(ratio - 9/16) < 0.1:
            return "9:16"
        elif abs(ratio - 4/3) < 0.1:
            return "4:3"
        elif abs(ratio - 3/4) < 0.1:
            return "3:4"
        else:
            return "1:1"  # Default to square
    
    def _get_negative_prompt(
        self,
        guidelines: Optional[ComprehensiveBrandGuidelines]
    ) -> str:
        """Build negative prompt from prohibited elements."""
        if not guidelines or not guidelines.prohibited_elements:
            return ""
        
        return ", ".join(guidelines.prohibited_elements[:5])
    
    def get_backend_name(self) -> str:
        """Return backend name."""
        return "Google Gemini Imagen 4"
    
    def validate_config(self) -> tuple[bool, list[str]]:
        """Validate Gemini configuration."""
        errors = []
        if not self.api_key:
            errors.append("GEMINI_API_KEY is required")
        return len(errors) == 0, errors
