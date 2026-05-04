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
        self.CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
        
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
                "CLAUDE_API_KEY not set - guideline extraction and localization "
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
