"""Claude image service placeholder (future capability)."""

from src.genai.base import ImageGenerationService
from src.models import ComprehensiveBrandGuidelines


class ClaudeImageService(ImageGenerationService):
    """
    Placeholder for future Claude image generation capabilities.

    Note: As of January 2026, Claude (Anthropic) can analyze images but does not
    yet support image generation. This service is included as a placeholder for
    future compatibility when/if Anthropic adds image generation capabilities.
    """

    def __init__(self, api_key: str | None = None, max_retries: int = 3):
        super().__init__(api_key=api_key or "", max_retries=max_retries)

    async def generate_image(
        self, prompt: str, size: str = "1024x1024", brand_guidelines: ComprehensiveBrandGuidelines | None = None
    ) -> bytes:
        """Not yet implemented - Claude doesn't support image generation."""
        raise NotImplementedError(
            "Claude (Anthropic) does not currently support image generation. "
            "This backend is a placeholder for future compatibility. "
            "Please use: 'firefly', 'openai', or 'gemini' instead."
        )

    def get_backend_name(self) -> str:
        """Return backend name."""
        return "Claude (Not Available)"

    def validate_config(self) -> tuple[bool, list[str]]:
        """Validate configuration."""
        return False, ["Claude image generation is not yet available"]
