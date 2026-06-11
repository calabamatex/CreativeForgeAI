"""Configuration management using environment variables."""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
import structlog

logger = structlog.get_logger(__name__)

# Load environment variables
load_dotenv()


class Config:
    """Main configuration class."""
    
    def __init__(self):
        # Adobe Firefly API Keys
        self.FIREFLY_API_KEY = os.getenv("FIREFLY_API_KEY")
        self.FIREFLY_CLIENT_ID = os.getenv("FIREFLY_CLIENT_ID")
        
        # OpenAI API Key
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        
        # Google Gemini API Key
        self.GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
        
        # Anthropic Claude API Key (for text processing)
        # Canonical name is ANTHROPIC_API_KEY (Anthropic SDK convention);
        # CLAUDE_API_KEY is accepted as a fallback for backwards compatibility.
        self.CLAUDE_API_KEY = os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")
        
        # Default Image Generation Backend
        self.DEFAULT_IMAGE_BACKEND = os.getenv("DEFAULT_IMAGE_BACKEND", "firefly").lower()
        
        # Feature Flags
        self.ENABLE_CLAUDE_INTEGRATION = os.getenv("ENABLE_CLAUDE_INTEGRATION", "true").lower() == "true"
        self.ENABLE_EXTERNAL_GUIDELINES = os.getenv("ENABLE_EXTERNAL_GUIDELINES", "true").lower() == "true"
        self.ENABLE_LOCALIZATION = os.getenv("ENABLE_LOCALIZATION", "true").lower() == "true"
        
        # Performance
        self.MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", "5"))
        self.API_TIMEOUT = int(os.getenv("API_TIMEOUT", "30"))
        self.MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
        
        # Paths
        self.OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "./output"))
        self.TEMP_DIR = Path(os.getenv("TEMP_DIR", "./temp"))
        
        # Create directories
        self.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        self.TEMP_DIR.mkdir(parents=True, exist_ok=True)
        
        # Image Settings
        self.DEFAULT_IMAGE_SIZE = (1024, 1024)
        self.SUPPORTED_FORMATS = ["png", "jpg", "jpeg"]
        
        # API Endpoints
        self.FIREFLY_API_URL = "https://firefly-api.adobe.io/v3/images/generate"
        self.CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"
        
        # Logging
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

        # ---------------------------------------------------------------
        # Image-generation cost model (per generated image, USD).
        #
        # These are the documented public list prices for a single
        # standard-resolution (~1024x1024) image as of 2026-06, used to
        # turn the pipeline's real ``total_api_calls`` into an honest
        # ``cost_estimate_usd``. Each price has a verifiable public source:
        #
        #   * firefly  -- $0.04/image: Adobe Firefly Services image
        #                 generation (1 generative credit, $0.04/credit on
        #                 the pay-as-you-go enterprise tier).
        #   * openai   -- $0.04/image: OpenAI Images API, gpt-image-1 /
        #                 DALL-E 3 standard 1024x1024.
        #   * gemini   -- $0.04/image: Google Imagen on Vertex AI,
        #                 imagegeneration standard 1024x1024.
        #
        # Override any/all via the IMAGE_BACKEND_PRICES env var as a
        # comma-separated ``name:price`` list, e.g.
        #   IMAGE_BACKEND_PRICES="firefly:0.05,openai:0.04,gemini:0.03"
        # Backends with no known price (e.g. the test "fake" backend) are
        # treated as $0.00 and are NOT counted into the cost estimate.
        # ---------------------------------------------------------------
        self.IMAGE_BACKEND_PRICES: dict[str, float] = self._load_image_backend_prices()

    # Canonical (public list price) defaults, USD per generated image.
    DEFAULT_IMAGE_BACKEND_PRICES: dict[str, float] = {
        "firefly": 0.04,
        "openai": 0.04,
        "gemini": 0.04,
    }

    # Backend-name aliases -> canonical price-table key.
    _BACKEND_ALIASES: dict[str, str] = {
        "dall-e": "openai",
        "dalle": "openai",
        "imagen": "gemini",
    }

    def _load_image_backend_prices(self) -> dict[str, float]:
        """Build the per-backend price table, applying any env override.

        Starts from :data:`DEFAULT_IMAGE_BACKEND_PRICES` and overlays
        entries parsed from the ``IMAGE_BACKEND_PRICES`` env var
        (``name:price`` comma-separated). Malformed entries are skipped
        with a warning rather than crashing config load.
        """
        prices = dict(self.DEFAULT_IMAGE_BACKEND_PRICES)
        raw = os.getenv("IMAGE_BACKEND_PRICES")
        if raw:
            for entry in raw.split(","):
                entry = entry.strip()
                if not entry:
                    continue
                name, sep, value = entry.partition(":")
                if not sep:
                    logger.warning("config.image_price_malformed", entry=entry)
                    continue
                try:
                    prices[name.strip().lower()] = float(value.strip())
                except ValueError:
                    logger.warning("config.image_price_invalid", entry=entry)
        return prices

    def get_image_unit_price(self, backend: str | None) -> float:
        """Return the USD list price for one image from *backend*.

        Resolves aliases (``dall-e`` -> ``openai``, ``imagen`` -> ``gemini``)
        and returns ``0.0`` for unknown backends (e.g. the test "fake"
        backend), so unpriced backends contribute nothing to a cost estimate.
        """
        if not backend:
            return 0.0
        key = backend.strip().lower()
        key = self._BACKEND_ALIASES.get(key, key)
        return self.IMAGE_BACKEND_PRICES.get(key, 0.0)

    def estimate_image_cost_usd(
        self, backend: str | None, api_calls: int
    ) -> float:
        """Estimate the USD cost of *api_calls* images on *backend*.

        ``cost = api_calls x unit_price(backend)``. Returns ``0.0`` for
        unpriced backends. Rounded to 4 decimal places (sub-cent fidelity).
        """
        unit = self.get_image_unit_price(backend)
        return round(max(api_calls, 0) * unit, 4)

    def validate(self) -> tuple[bool, list[str]]:
        """Validate configuration."""
        errors = []
        warnings = []
        
        # Check if at least one image backend is configured
        has_image_backend = False
        
        if self.FIREFLY_API_KEY and self.FIREFLY_CLIENT_ID:
            has_image_backend = True
        if self.OPENAI_API_KEY:
            has_image_backend = True
        if self.GEMINI_API_KEY:
            has_image_backend = True
        
        if not has_image_backend:
            errors.append(
                "At least one image generation backend must be configured: "
                "Firefly (FIREFLY_API_KEY + FIREFLY_CLIENT_ID), "
                "OpenAI (OPENAI_API_KEY), or "
                "Gemini (GEMINI_API_KEY)"
            )
        
        # Check Claude for text processing (optional but recommended)
        if self.ENABLE_CLAUDE_INTEGRATION and not self.CLAUDE_API_KEY:
            warnings.append(
                "ANTHROPIC_API_KEY not set - guideline extraction and localization "
                "will use fallback methods"
            )
        
        # Validate default backend
        valid_backends = ["firefly", "openai", "dall-e", "dalle", "gemini", "imagen"]
        if self.DEFAULT_IMAGE_BACKEND not in valid_backends:
            errors.append(
                f"Invalid DEFAULT_IMAGE_BACKEND: '{self.DEFAULT_IMAGE_BACKEND}'. "
                f"Must be one of: {', '.join(valid_backends)}"
            )
        
        if warnings:
            for warning in warnings:
                logger.warning("config.validation_warning", warning=warning)
        
        return len(errors) == 0, errors
    
    def get_available_backends(self) -> list[str]:
        """Return list of available (configured) image backends."""
        available = []
        
        if self.FIREFLY_API_KEY and self.FIREFLY_CLIENT_ID:
            available.append("firefly")
        if self.OPENAI_API_KEY:
            available.extend(["openai", "dall-e", "dalle"])
        if self.GEMINI_API_KEY:
            available.extend(["gemini", "imagen"])
        
        return available


# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get global config instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config


def reload_config() -> Config:
    """Reload configuration."""
    global _config
    _config = Config()
    return _config
