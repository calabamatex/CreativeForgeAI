"""
Pytest configuration and shared fixtures for test suite.

===========================================================================
THREE-TIER TEST TAXONOMY + COST GATING  (P6-T1)
===========================================================================

Tests fall into three cost tiers, enforced here so the DEFAULT ``pytest``
run is always cheap, fast, and safe (no money spent, no surprise API calls):

  * ``unit``        -- no real I/O, everything mocked. The DEFAULT tier:
                       every test NOT under ``tests/integration/`` is auto-
                       tagged ``unit`` (see ``pytest_collection_modifyitems``).
  * ``integration`` -- real Postgres / Redis / MinIO from the dev stack, but
                       NO paid provider calls. Every test under
                       ``tests/integration/`` is auto-tagged ``integration``.
  * ``paid``        -- makes REAL paid provider calls (Firefly / OpenAI /
                       Gemini / Anthropic) that COST MONEY. SKIPPED by default.

Auto-tagging (so the taxonomy is enforced without hand-marking every test):
``pytest_collection_modifyitems`` applies ``integration`` to everything under
``tests/integration/`` and ``unit`` to the rest. An EXPLICIT marker on a test
is never overridden (e.g. a ``unit`` test physically placed under
``tests/integration/`` keeps its ``unit`` marker, and vice-versa).

Cost gating:
  * ``paid`` tests are SKIPPED unless ``RUN_PAID_TESTS=1`` is set in the env.
    So a bare ``pytest`` (and the PR-CI gate) never spends money. To actually
    run them:  ``RUN_PAID_TESTS=1 pytest -m paid``.
  * ``paid_matrix`` tests (the full backend x locale x ratio worst case, ~45
    paid calls) are gated EVEN HARDER: they require BOTH ``RUN_PAID_TESTS=1``
    AND ``RUN_FULL_MATRIX=1``. This keeps the ~45-call worst case behind a
    SEPARATE explicit flag so it can never land in the default or PR-CI path,
    even when someone opts into ``RUN_PAID_TESTS=1`` for a single provider
    smoke test. There is no matrix test on this branch yet (P2-T1's Firefly
    live test was deferred); this documents + enforces the convention so it
    cannot accidentally be added to the default path when it lands.

See ``docs/FOUND_ISSUES.md`` and the README testing notes for the full policy.
"""

import importlib
import os
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Tier auto-tagging + paid cost-gating  (P6-T1)
# ---------------------------------------------------------------------------

# Resolve the integration test root once (tests/integration/) so location-based
# auto-tagging works regardless of where pytest is invoked from.
_INTEGRATION_DIR = Path(__file__).parent / "integration"


def pytest_collection_modifyitems(config, items):
    """Enforce the three-tier taxonomy at collection time.

    Two responsibilities:

    1. **Auto-tag tiers by location** -- apply ``integration`` to tests under
       ``tests/integration/`` and ``unit`` to everything else, WITHOUT
       overriding any explicit ``unit``/``integration`` marker a test already
       carries. This keeps the taxonomy enforced without hand-marking files.

    2. **Cost-gate paid tests** -- attach a SKIP to any ``paid`` test unless
       ``RUN_PAID_TESTS=1``; ``paid_matrix`` tests additionally require
       ``RUN_FULL_MATRIX=1``. So a bare ``pytest`` never spends money and the
       ~45-call matrix is double-gated behind its own explicit flag.
    """
    run_paid = os.getenv("RUN_PAID_TESTS") == "1"
    run_matrix = os.getenv("RUN_FULL_MATRIX") == "1"

    skip_paid = pytest.mark.skip(reason="paid test — set RUN_PAID_TESTS=1 to run")
    skip_matrix = pytest.mark.skip(reason="full paid matrix — set RUN_PAID_TESTS=1 and RUN_FULL_MATRIX=1 to run")

    for item in items:
        own_markers = {m.name for m in item.iter_markers()}

        # --- (1) location-based tier auto-tagging (don't override explicit) ---
        if "unit" not in own_markers and "integration" not in own_markers:
            try:
                in_integration = _INTEGRATION_DIR in Path(item.fspath).parents
            except Exception:
                in_integration = False
            item.add_marker("integration" if in_integration else "unit")

        # --- (2) paid cost-gating -----------------------------------------
        if "paid_matrix" in own_markers:
            if not (run_paid and run_matrix):
                item.add_marker(skip_matrix)
        elif "paid" in own_markers:
            if not run_paid:
                item.add_marker(skip_paid)


# ---------------------------------------------------------------------------
# Per-test isolation of process-global config state  (P6-T1 flake fix)
# ---------------------------------------------------------------------------
#
# ``src/config.py`` keeps a module-level ``Config`` singleton (``_config``)
# built from ``os.environ`` at first access. Tests that mutate ``os.environ``
# (e.g. ``mock_env_vars``, or the CLI tests that clear FIREFLY/OPENAI/... keys)
# or that reset ``config._config = None`` can leak that state into a LATER test,
# making order-dependent failures like
# ``test_cli.py::test_validate_config_command`` (passes alone, fails in the full
# suite). Historically the suite "worked" only because such leaked keys happened
# to flow forward into the parser/pipeline/genai unit tests, which instantiate
# ``ClaudeService()`` etc. WITHOUT passing a key and rely on config having one.
#
# This autouse fixture makes config-dependent tests ORDER-INDEPENDENT by:
#   1. snapshotting ``os.environ`` and resetting the ``src.config`` singleton,
#   2. establishing a deterministic BASELINE of fake test API keys + backend so
#      every test starts from the same known-good config (no reliance on leakage
#      from an earlier test), and
#   3. at teardown, restoring the original environment exactly and dropping the
#      singleton so nothing leaks forward.
#
# Tests that specifically exercise MISSING config (e.g.
# ``test_validate_config_missing_keys``) still work: they ``monkeypatch.delenv``
# the keys AFTER this baseline is applied, and monkeypatch's own teardown +
# this fixture's restore both run, so the baseline never leaks either.

# Deterministic baseline of fake credentials for unit tests. These are NOT real
# keys (no paid calls are ever made in unit/integration tiers); they exist only
# so config-dependent constructors don't blow up on a missing key.
_BASELINE_TEST_ENV: dict[str, str] = {
    "FIREFLY_API_KEY": "test-firefly-key",
    "FIREFLY_CLIENT_ID": "test-firefly-client",
    "OPENAI_API_KEY": "test-openai-key",
    "GEMINI_API_KEY": "test-gemini-key",
    # Only CLAUDE_API_KEY (the legacy fallback) is set here, NOT
    # ANTHROPIC_API_KEY: ``Config`` resolves ``CLAUDE_API_KEY`` as
    # ``ANTHROPIC_API_KEY or CLAUDE_API_KEY``, and the existing
    # ``mock_env_vars`` fixture / ``test_config_loads_all_keys`` assert the
    # value is exactly ``test-claude-key``. Setting ANTHROPIC_API_KEY would win
    # over it and break that assertion, so we mirror ``mock_env_vars`` exactly.
    "CLAUDE_API_KEY": "test-claude-key",
    "DEFAULT_IMAGE_BACKEND": "firefly",
}


@pytest.fixture(autouse=True)
def _isolate_env_and_config():
    """Snapshot/restore ``os.environ`` + reset the ``src.config`` singleton.

    Runs around EVERY test (autouse). Guarantees config-dependent tests cannot
    leak env/singleton state into each other regardless of collection order, and
    that each test starts from a deterministic baseline of fake test keys.
    """
    env_snapshot = dict(os.environ)

    try:
        config = importlib.import_module("src.config")
    except Exception:
        config = None

    # Apply the deterministic baseline so config-dependent tests are
    # self-sufficient and order-independent (don't override anything a real
    # value is already providing for non-key vars; keys are forced to the
    # known fake values to avoid empty-string leakage from .env).
    for key, value in _BASELINE_TEST_ENV.items():
        os.environ[key] = value

    # Build a fresh Config from the baseline-applied environment.
    if config is not None:
        config._config = None

    try:
        yield
    finally:
        # Restore the exact environment the test started with.
        os.environ.clear()
        os.environ.update(env_snapshot)
        # Drop any singleton this test built so the next test starts clean and
        # rebuilds from the restored environment.
        if config is not None:
            config._config = None


@pytest.fixture
def example_product():
    """Example product for testing."""
    return {
        "product_id": "TEST-PROD-001",
        "product_name": "Test Product",
        "product_description": "A test product for unit testing",
        "product_category": "Electronics",
        "key_features": ["Feature 1", "Feature 2", "Feature 3"],
        "generation_prompt": "professional product photo of test product",
    }


@pytest.fixture
def example_campaign_message():
    """Example campaign message for testing."""
    return {"locale": "en-US", "headline": "Test Headline", "subheadline": "Test Subheadline", "cta": "Test CTA"}


@pytest.fixture
def example_brief(example_product, example_campaign_message):
    """Example campaign brief for testing."""
    return {
        "campaign_id": "TEST-CAMPAIGN-001",
        "campaign_name": "Test Campaign",
        "brand_name": "Test Brand",
        "target_market": "North America",
        "target_audience": "Test audience",
        "campaign_message": example_campaign_message,
        "products": [example_product],
        "aspect_ratios": ["1:1", "9:16"],
        "output_formats": ["png"],
        "image_generation_backend": "firefly",
        "enable_localization": True,
        "target_locales": ["en-US", "es-MX"],
    }


@pytest.fixture
def mock_image_bytes():
    """Mock image bytes for testing."""
    from io import BytesIO

    from PIL import Image

    # Create a valid test image
    img = Image.new("RGB", (1024, 1024), color="blue")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def mock_firefly_response():
    """Mock Adobe Firefly API response."""
    return {"outputs": [{"image": {"url": "https://example.com/generated-image.jpg"}}]}


@pytest.fixture
def mock_openai_response():
    """Mock OpenAI DALL-E API response."""
    return {"data": [{"url": "https://example.com/dalle-image.png"}]}


@pytest.fixture
def mock_gemini_response():
    """Mock Google Gemini API response."""
    return {
        "predictions": [
            {
                "bytesBase64Encoded": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
            }
        ]
    }


@pytest.fixture
def mock_claude_response():
    """Mock Anthropic Claude API response."""
    return {
        "id": "msg_123",
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": '{"result": "test response"}'}],
        "model": "claude-sonnet-4-20250514",
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 100, "output_tokens": 50},
    }


@pytest.fixture
def brand_guidelines_text():
    """Example brand guidelines text for testing."""
    return """
    Brand Guidelines

    Primary Colors: #0066CC, #1A1A1A
    Secondary Colors: #FFFFFF, #F5F5F5

    Typography:
    Primary Font: Montserrat
    Secondary Font: Open Sans

    Brand Voice: Professional, innovative, customer-focused

    Photography Style: Clean, modern, minimalist product photography
    with natural lighting and neutral backgrounds.

    Logo Usage:
    - Minimum clearspace: 20px
    - Minimum size: 50px

    Prohibited Uses:
    - Do not use dark or busy backgrounds
    - Avoid cluttered compositions

    Approved Taglines:
    - "Innovation at Your Fingertips"
    - "Designed for Tomorrow"
    """


@pytest.fixture
def localization_rules_yaml():
    """Example localization rules in YAML format."""
    return """
    market_specific_rules:
      en-US:
        tone: casual
        formality: informal
        preferred_style: direct
      es-MX:
        tone: warm
        formality: formal
        preferred_style: respectful
      fr-CA:
        tone: professional
        formality: formal
        preferred_style: polite

    prohibited_terms:
      en-US:
        - cheap
        - discount
      es-MX:
        - barato
        - oferta
      fr-CA:
        - rabais

    translation_glossary:
      en-US:
        product: product
        quality: quality
      es-MX:
        product: producto
        quality: calidad
      fr-CA:
        product: produit
        quality: qualité

    tone_guidelines:
      en-US: "Be direct and clear, use active voice"
      es-MX: "Be warm and respectful, use formal pronouns"
      fr-CA: "Be professional and polite, maintain formal tone"

    cultural_considerations:
      en-US:
        - Emphasize innovation and convenience
        - Use conversational language
      es-MX:
        - Show respect for family values
        - Use formal address when appropriate
      fr-CA:
        - Respect bilingual nature
        - Use inclusive language
    """


@pytest.fixture
def brand_guidelines_model():
    """Example brand guidelines model for testing."""
    from src.models import ComprehensiveBrandGuidelines

    return ComprehensiveBrandGuidelines(
        source_file="test_guidelines.pdf",
        primary_colors=["#0066CC", "#1A1A1A"],
        secondary_colors=["#FFFFFF", "#F5F5F5"],
        primary_font="Montserrat",
        secondary_font="Open Sans",
        brand_voice="Professional, innovative, customer-focused",
        photography_style="Clean, modern, minimalist product photography",
        logo_clearspace=20,
        logo_min_size=50,
        prohibited_uses=["No dark backgrounds", "No cluttered compositions"],
        approved_taglines=["Innovation at Your Fingertips"],
    )


@pytest.fixture
def localization_guidelines_model():
    """Example localization guidelines model for testing."""
    from src.models import LocalizationGuidelines

    return LocalizationGuidelines(
        source_file="test_localization.yaml",
        supported_locales=["en-US", "es-MX", "fr-CA"],
        market_specific_rules={
            "en-US": {"tone": "casual", "formality": "informal"},
            "es-MX": {"tone": "warm", "formality": "formal"},
            "fr-CA": {"tone": "professional", "formality": "formal"},
        },
        prohibited_terms={"en-US": ["cheap", "discount"], "es-MX": ["barato", "oferta"]},
        translation_glossary={"en-US": {"product": "product"}, "es-MX": {"product": "producto"}},
    )


@pytest.fixture
def temp_output_dir(tmp_path):
    """Temporary output directory for testing."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    return output_dir


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Mock environment variables for testing."""
    monkeypatch.setenv("FIREFLY_API_KEY", "test-firefly-key")
    monkeypatch.setenv("FIREFLY_CLIENT_ID", "test-firefly-client")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("CLAUDE_API_KEY", "test-claude-key")
    monkeypatch.setenv("DEFAULT_IMAGE_BACKEND", "firefly")
