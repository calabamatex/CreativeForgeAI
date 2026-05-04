"""Abstract base class for image generation services."""
from abc import ABC, abstractmethod
from typing import Optional
import aiohttp
import structlog
from src.models import ComprehensiveBrandGuidelines
from src.security import sanitize_prompt

logger = structlog.get_logger(__name__)


class ImageGenerationService(ABC):
    """Abstract base class for all image generation backends."""

    def __init__(self, api_key: str, max_retries: int = 3):
        self.api_key = api_key
        self.max_retries = max_retries
        self.backend_name = self.__class__.__name__
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create a shared HTTP session with connection pooling and timeouts."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(
                total=120,
                connect=10,
                sock_read=60,
            )
            connector = aiohttp.TCPConnector(
                limit=20,
                limit_per_host=10,
                ttl_dns_cache=300,
                enable_cleanup_closed=True,
            )
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
            )
        return self._session

    async def close(self):
        """Close the shared HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
    
    @abstractmethod
    async def generate_image(
        self,
        prompt: str,
        size: str = "1024x1024",
        brand_guidelines: Optional[ComprehensiveBrandGuidelines] = None
    ) -> bytes:
        """
        Generate an image from text prompt.
        
        Args:
            prompt: Text description of the image to generate
            size: Image dimensions (format depends on backend)
            brand_guidelines: Optional brand guidelines to apply
            
        Returns:
            bytes: Raw image data
        """
        pass
    
    def _sanitize_prompt(self, prompt: str) -> str:
        """Sanitize a prompt: strip control characters, enforce max length."""
        return sanitize_prompt(prompt)

    def _build_brand_compliant_prompt(
        self,
        base_prompt: str,
        guidelines: Optional[ComprehensiveBrandGuidelines]
    ) -> str:
        """
        Enhance prompt with brand guidelines and sanitize the result.

        This is a shared utility method that all backends can use.
        """
        if not guidelines:
            return self._sanitize_prompt(base_prompt)

        enhanced = base_prompt

        if guidelines.photography_style:
            enhanced += f", {guidelines.photography_style}"

        if guidelines.brand_voice:
            enhanced += f", {guidelines.brand_voice} aesthetic"

        # Add prohibitions as negative prompts
        if guidelines.prohibited_elements:
            enhanced += f". Avoid: {', '.join(guidelines.prohibited_elements[:3])}"

        return self._sanitize_prompt(enhanced)
    
    @abstractmethod
    def get_backend_name(self) -> str:
        """Return the backend name for logging/reporting."""
        pass
    
    @abstractmethod
    def validate_config(self) -> tuple[bool, list[str]]:
        """Validate backend configuration."""
        pass
