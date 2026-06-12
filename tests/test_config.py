"""
Tests for configuration management and environment variables.
"""

import os


class TestConfig:
    """Test Config class and environment variable loading."""

    def test_config_loads_all_keys(self, mock_env_vars):
        """Test that config loads all required API keys."""
        from src.config import reload_config

        config = reload_config()

        assert config.FIREFLY_API_KEY == "test-firefly-key"
        assert config.FIREFLY_CLIENT_ID == "test-firefly-client"
        assert config.OPENAI_API_KEY == "test-openai-key"
        assert config.GEMINI_API_KEY == "test-gemini-key"
        assert config.CLAUDE_API_KEY == "test-claude-key"

    def test_config_default_backend(self, mock_env_vars):
        """Test default backend configuration."""
        from src.config import reload_config

        config = reload_config()

        assert config.DEFAULT_IMAGE_BACKEND == "firefly"

    def test_config_get_available_backends(self, mock_env_vars):
        """Test getting list of available backends."""
        from src.config import reload_config

        config = reload_config()
        available = config.get_available_backends()

        assert "firefly" in available
        assert "openai" in available or "dall-e" in available
        assert "gemini" in available or "imagen" in available

    def test_config_partial_backends(self, monkeypatch):
        """Test config with only some backends configured."""
        # Clear all env vars first
        for key in list(os.environ.keys()):
            if any(k in key for k in ["FIREFLY", "OPENAI", "GEMINI", "CLAUDE", "DEFAULT"]):
                monkeypatch.delenv(key, raising=False)

        monkeypatch.setenv("FIREFLY_API_KEY", "test-key")
        monkeypatch.setenv("FIREFLY_CLIENT_ID", "test-client")
        monkeypatch.setenv("CLAUDE_API_KEY", "test-claude")
        # Don't set OpenAI or Gemini

        from src.config import reload_config

        config = reload_config()
        available = config.get_available_backends()

        assert "firefly" in available
        assert not any(b in available for b in ["openai", "dall-e", "dalle"])
        assert not any(b in available for b in ["gemini", "imagen"])

    def test_config_validate_success(self, mock_env_vars):
        """Test config validation with all required keys."""
        from src.config import reload_config

        config = reload_config()
        is_valid, errors = config.validate()

        assert is_valid is True
        assert len(errors) == 0

    def test_config_validate_missing_claude_is_warning_only(self, monkeypatch):
        """Test config validation succeeds without Claude key (warning only)."""
        # Clear all env vars first
        for key in list(os.environ.keys()):
            if any(k in key for k in ["FIREFLY", "OPENAI", "GEMINI", "CLAUDE", "DEFAULT"]):
                monkeypatch.delenv(key, raising=False)

        monkeypatch.setenv("FIREFLY_API_KEY", "test-key")
        monkeypatch.setenv("FIREFLY_CLIENT_ID", "test-client")
        # Don't set CLAUDE_API_KEY - should only be a warning

        from src.config import reload_config

        config = reload_config()
        is_valid, errors = config.validate()

        # Claude is optional - validation should still pass
        assert is_valid is True
        assert len(errors) == 0

    def test_config_validate_no_image_backends(self, monkeypatch):
        """Test config validation fails without any image backend."""
        # Clear all env vars first
        for key in list(os.environ.keys()):
            if any(k in key for k in ["FIREFLY", "OPENAI", "GEMINI", "CLAUDE", "DEFAULT"]):
                monkeypatch.delenv(key, raising=False)

        monkeypatch.setenv("CLAUDE_API_KEY", "test-claude")
        # Don't set any image generation backend keys

        from src.config import reload_config

        config = reload_config()
        is_valid, errors = config.validate()

        assert is_valid is False
        assert any("image" in error.lower() for error in errors)

    def test_config_output_dir(self, mock_env_vars):
        """Test output directory configuration."""
        from src.config import reload_config

        config = reload_config()

        assert config.OUTPUT_DIR is not None
        assert "output" in str(config.OUTPUT_DIR).lower()

    def test_config_singleton_pattern(self, mock_env_vars):
        """Test that get_config returns same instance."""
        from src.config import get_config

        # Use get_config (not reload_config) to test singleton
        config1 = get_config()
        config2 = get_config()

        assert config1 is config2

    def test_config_firefly_url(self, mock_env_vars):
        """Test Firefly API URL configuration."""
        from src.config import reload_config

        config = reload_config()

        assert config.FIREFLY_API_URL is not None
        assert "firefly" in config.FIREFLY_API_URL.lower()

    def test_config_max_concurrent_requests(self, mock_env_vars):
        """Test max concurrent requests configuration."""
        from src.config import reload_config

        config = reload_config()

        assert config.MAX_CONCURRENT_REQUESTS > 0
        assert isinstance(config.MAX_CONCURRENT_REQUESTS, int)

    def test_config_timeout_settings(self, mock_env_vars):
        """Test API timeout configuration."""
        from src.config import reload_config

        config = reload_config()

        assert config.API_TIMEOUT > 0
        assert isinstance(config.API_TIMEOUT, int)

    def test_config_max_retries(self, mock_env_vars):
        """Test max retries configuration."""
        from src.config import reload_config

        config = reload_config()

        assert config.MAX_RETRIES >= 0
        assert isinstance(config.MAX_RETRIES, int)

    def test_config_backend_normalization(self, monkeypatch):
        """Test that backend names are normalized to lowercase."""
        # Clear all env vars first
        for key in list(os.environ.keys()):
            if any(k in key for k in ["FIREFLY", "OPENAI", "GEMINI", "CLAUDE", "DEFAULT"]):
                monkeypatch.delenv(key, raising=False)

        monkeypatch.setenv("DEFAULT_IMAGE_BACKEND", "FIREFLY")
        monkeypatch.setenv("FIREFLY_API_KEY", "test")
        monkeypatch.setenv("FIREFLY_CLIENT_ID", "test")
        monkeypatch.setenv("CLAUDE_API_KEY", "test")

        from src.config import reload_config

        config = reload_config()

        assert config.DEFAULT_IMAGE_BACKEND == "firefly"

    def test_config_feature_flags(self, mock_env_vars):
        """Test feature flag configuration."""
        from src.config import reload_config

        config = reload_config()

        # These should have defaults even if not set
        assert hasattr(config, "ENABLE_CLAUDE_INTEGRATION")
        assert hasattr(config, "ENABLE_LOCALIZATION")


class TestConfigIntegration:
    """Integration tests for config usage."""

    def test_config_used_by_services(self, mock_env_vars):
        """Test that services can access config."""
        from src.config import reload_config

        config = reload_config()

        # Verify all services can get their required config
        assert config.FIREFLY_API_KEY is not None
        assert config.CLAUDE_API_KEY is not None

    def test_config_backend_selection_priority(self, mock_env_vars):
        """Test backend selection follows priority."""
        from src.config import reload_config

        config = reload_config()

        # When all backends are available, default should be used
        assert config.DEFAULT_IMAGE_BACKEND in config.get_available_backends()
