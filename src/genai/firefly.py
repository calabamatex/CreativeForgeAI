"""Adobe Firefly API service for image generation."""
import aiohttp
import asyncio
from typing import Optional
import structlog
from src.genai.base import ImageGenerationService
from src.models import ComprehensiveBrandGuidelines
from src.config import get_config

logger = structlog.get_logger(__name__)


class FireflyImageService(ImageGenerationService):
    """Service for generating images using Adobe Firefly API."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        client_id: Optional[str] = None,
        max_retries: int = 3
    ):
        config = get_config()
        super().__init__(
            api_key=api_key or config.FIREFLY_API_KEY,
            max_retries=max_retries
        )
        self.client_id = client_id or config.FIREFLY_CLIENT_ID
        self.api_url = config.FIREFLY_API_URL
    
    async def generate_image(
        self,
        prompt: str,
        size: str = "2048x2048",
        brand_guidelines: Optional[ComprehensiveBrandGuidelines] = None
    ) -> bytes:
        """Generate image using Firefly API."""
        
        # Sanitize and enhance prompt with brand guidelines
        if brand_guidelines:
            prompt = self._build_brand_compliant_prompt(prompt, brand_guidelines)
        else:
            prompt = self._sanitize_prompt(prompt)

        logger.debug("firefly.prompt", prompt=prompt)

        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        width, height = map(int, size.split('x'))
        
        payload = {
            "prompt": prompt,
            "size": {"width": width, "height": height},
            "contentClass": "photo",
            "n": 1
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
                        image_url = data["outputs"][0]["image"]["url"]
                        async with session.get(image_url) as img_response:
                            if img_response.status == 200:
                                return await img_response.read()
                            raise Exception(f"Image download failed: {img_response.status}")
                    elif response.status == 429:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    else:
                        error_text = await response.text()
                        logger.warning("firefly.api_error", status=response.status, error=error_text)
                        if attempt < self.max_retries - 1:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        raise Exception(f"Firefly API error: {response.status}")
            except asyncio.TimeoutError:
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise
        raise Exception("Max retries exceeded for Firefly API")
    
    def get_backend_name(self) -> str:
        """Return backend name."""
        return "Adobe Firefly"
    
    def validate_config(self) -> tuple[bool, list[str]]:
        """Validate Firefly configuration."""
        errors = []
        if not self.api_key:
            errors.append("FIREFLY_API_KEY is required")
        if not self.client_id:
            errors.append("FIREFLY_CLIENT_ID is required")
        return len(errors) == 0, errors
