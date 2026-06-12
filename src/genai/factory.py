"""Factory for creating image generation service instances."""

from src.genai.base import ImageGenerationService
from src.genai.claude_service_image import ClaudeImageService
from src.genai.firefly import FireflyImageService
from src.genai.gemini_service import GeminiImageService
from src.genai.openai_service import OpenAIImageService


class ImageGenerationFactory:
    """Factory for creating image generation service instances based on backend."""

    # Registry of available backends
    BACKENDS = {
        "firefly": FireflyImageService,
        "openai": OpenAIImageService,
        "dall-e": OpenAIImageService,  # Alias
        "dalle": OpenAIImageService,  # Alias
        "gemini": GeminiImageService,
        "imagen": GeminiImageService,  # Alias
        "claude": ClaudeImageService,  # Placeholder for future
    }

    @staticmethod
    def create(
        backend: str, api_key: str | None = None, client_id: str | None = None, max_retries: int = 3
    ) -> ImageGenerationService:
        """
        Create an image generation service instance.

        Args:
            backend: Backend name ('firefly', 'openai', 'gemini', 'claude')
            api_key: Optional API key (will use config if not provided)
            client_id: Optional client ID (Firefly only)
            max_retries: Maximum retry attempts

        Returns:
            ImageGenerationService instance

        Raises:
            ValueError: If backend is not supported
        """
        backend_lower = backend.lower()

        if backend_lower not in ImageGenerationFactory.BACKENDS:
            available = ", ".join(ImageGenerationFactory.BACKENDS.keys())
            raise ValueError(f"Unsupported backend: '{backend}'. Available backends: {available}")

        service_class = ImageGenerationFactory.BACKENDS[backend_lower]

        # Handle Firefly's special client_id parameter
        if backend_lower == "firefly":
            return service_class(api_key=api_key, client_id=client_id, max_retries=max_retries)
        else:
            return service_class(api_key=api_key, max_retries=max_retries)

    @staticmethod
    def list_backends() -> list[str]:
        """Return list of available backend names."""
        return list(ImageGenerationFactory.BACKENDS.keys())

    @staticmethod
    def get_default_backend() -> str:
        """Return the default backend."""
        return "firefly"
