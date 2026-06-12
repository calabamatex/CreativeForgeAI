"""
Tests for document parsers (brand guidelines and localization rules).
"""

import json
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest


class TestBrandGuidelinesParser:
    """Test brand guidelines parser."""

    @pytest.mark.asyncio
    async def test_parse_markdown_file(self, brand_guidelines_text, mock_claude_response):
        """Test parsing brand guidelines from markdown."""
        from src.genai.claude import ClaudeService
        from src.parsers.brand_parser import BrandGuidelinesParser

        # Create mock guidelines result
        extracted = {
            "source_file": "test.md",
            "primary_colors": ["#0066CC", "#1A1A1A"],
            "primary_font": "Montserrat",
            "brand_voice": "Professional",
            "photography_style": "Modern",
        }

        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=brand_guidelines_text)):
                with patch("aiohttp.ClientSession.post") as mock_post:
                    mock_response = AsyncMock()
                    mock_response.status = 200
                    mock_response.json = AsyncMock(
                        return_value={
                            "content": [{"text": json.dumps(extracted)}],
                            "usage": {"input_tokens": 100, "output_tokens": 50},
                        }
                    )
                    mock_post.return_value.__aenter__.return_value = mock_response

                    claude = ClaudeService()
                    parser = BrandGuidelinesParser(claude)
                    result = await parser.parse("test.md")

                    assert result is not None
                    assert result.source_file == "test.md"

    @pytest.mark.asyncio
    async def test_parse_with_claude(self, brand_guidelines_text):
        """Test parsing with Claude API."""
        from src.genai.claude import ClaudeService
        from src.parsers.brand_parser import BrandGuidelinesParser

        extracted = {
            "source_file": "test.md",
            "primary_colors": ["#0066CC", "#1A1A1A"],
            "primary_font": "Montserrat",
            "brand_voice": "Professional",
            "photography_style": "Modern",
        }

        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=brand_guidelines_text)):
                with patch("aiohttp.ClientSession.post") as mock_post:
                    mock_response = AsyncMock()
                    mock_response.status = 200
                    mock_response.json = AsyncMock(
                        return_value={
                            "content": [{"text": json.dumps(extracted)}],
                            "usage": {"input_tokens": 100, "output_tokens": 50},
                        }
                    )
                    mock_post.return_value.__aenter__.return_value = mock_response

                    claude = ClaudeService()
                    parser = BrandGuidelinesParser(claude)
                    result = await parser.parse("test.md")

                    assert result is not None
                    assert result.source_file == "test.md"

    @pytest.mark.asyncio
    async def test_parse_pdf_file(self, brand_guidelines_text):
        """Test parsing brand guidelines from PDF."""
        from src.genai.claude import ClaudeService
        from src.parsers.brand_parser import BrandGuidelinesParser

        extracted = {
            "source_file": "test.pdf",
            "primary_colors": ["#0066CC"],
            "primary_font": "Arial",
            "brand_voice": "Professional",
        }

        # Mock PyMuPDF
        mock_page = MagicMock()
        mock_page.get_text.return_value = brand_guidelines_text
        mock_doc = MagicMock()
        mock_doc.__enter__.return_value = [mock_page]
        mock_doc.__exit__.return_value = None

        with patch("pathlib.Path.exists", return_value=True):
            with patch("fitz.open", return_value=mock_doc):
                with patch("aiohttp.ClientSession.post") as mock_post:
                    mock_response = AsyncMock()
                    mock_response.status = 200
                    mock_response.json = AsyncMock(
                        return_value={
                            "content": [{"text": json.dumps(extracted)}],
                            "usage": {"input_tokens": 100, "output_tokens": 50},
                        }
                    )
                    mock_post.return_value.__aenter__.return_value = mock_response

                    claude = ClaudeService()
                    parser = BrandGuidelinesParser(claude)
                    result = await parser.parse("test.pdf")

                    assert result is not None
                    assert result.source_file == "test.pdf"

    @pytest.mark.asyncio
    async def test_parse_docx_file(self, brand_guidelines_text):
        """Test parsing brand guidelines from DOCX."""
        from src.genai.claude import ClaudeService
        from src.parsers.brand_parser import BrandGuidelinesParser

        extracted = {"source_file": "test.docx", "primary_colors": ["#0066CC"], "primary_font": "Montserrat"}

        # Mock python-docx
        mock_para = MagicMock()
        mock_para.text = brand_guidelines_text
        mock_doc = MagicMock()
        mock_doc.paragraphs = [mock_para]

        with patch("pathlib.Path.exists", return_value=True):
            with patch("docx.Document", return_value=mock_doc):
                with patch("aiohttp.ClientSession.post") as mock_post:
                    mock_response = AsyncMock()
                    mock_response.status = 200
                    mock_response.json = AsyncMock(
                        return_value={
                            "content": [{"text": json.dumps(extracted)}],
                            "usage": {"input_tokens": 100, "output_tokens": 50},
                        }
                    )
                    mock_post.return_value.__aenter__.return_value = mock_response

                    claude = ClaudeService()
                    parser = BrandGuidelinesParser(claude)
                    result = await parser.parse("test.docx")

                    assert result is not None
                    assert result.source_file == "test.docx"


class TestLocalizationGuidelinesParser:
    """Test localization guidelines parser."""

    @pytest.mark.asyncio
    async def test_parse_yaml_file(self, localization_rules_yaml):
        """Test parsing YAML localization rules."""
        from src.genai.claude import ClaudeService
        from src.parsers.localization_parser import LocalizationGuidelinesParser

        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=localization_rules_yaml)):
                parser = LocalizationGuidelinesParser(ClaudeService())
                result = await parser.parse("test.yaml")

                assert result is not None
                assert result.source_file == "test.yaml"
                assert len(result.supported_locales) == 0  # Not in YAML data

    @pytest.mark.asyncio
    async def test_parse_json_file(self):
        """Test parsing JSON localization rules."""
        from src.genai.claude import ClaudeService
        from src.parsers.localization_parser import LocalizationGuidelinesParser

        json_data = {
            "market_specific_rules": {"en-US": {"tone": "casual"}},
            "prohibited_terms": {},
            "translation_glossary": {},
        }

        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=json.dumps(json_data))):
                parser = LocalizationGuidelinesParser(ClaudeService())
                result = await parser.parse("test.json")

                assert result is not None
                assert "en-US" in result.market_specific_rules

    @pytest.mark.asyncio
    async def test_parse_yaml_structure(self, localization_rules_yaml):
        """Test parsing structured YAML format."""
        from src.genai.claude import ClaudeService
        from src.parsers.localization_parser import LocalizationGuidelinesParser

        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=localization_rules_yaml)):
                parser = LocalizationGuidelinesParser(ClaudeService())
                result = await parser.parse("test.yaml")

                assert result.source_file == "test.yaml"
                assert "en-US" in result.market_specific_rules
                assert "es-MX" in result.market_specific_rules

    @pytest.mark.asyncio
    async def test_parse_markdown_with_claude(self):
        """Test parsing markdown localization rules with Claude."""
        from src.genai.claude import ClaudeService
        from src.parsers.localization_parser import LocalizationGuidelinesParser

        markdown_text = """
        # Localization Rules

        en-US: Casual tone
        es-MX: Formal tone
        """

        extracted = {
            "source_file": "test.md",
            "market_specific_rules": {"en-US": {"tone": "casual"}, "es-MX": {"tone": "formal"}},
            "prohibited_terms": {},
            "translation_glossary": {},
        }

        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=markdown_text)):
                with patch("aiohttp.ClientSession.post") as mock_post:
                    mock_response = AsyncMock()
                    mock_response.status = 200
                    mock_response.json = AsyncMock(
                        return_value={
                            "content": [{"text": json.dumps(extracted)}],
                            "usage": {"input_tokens": 100, "output_tokens": 50},
                        }
                    )
                    mock_post.return_value.__aenter__.return_value = mock_response

                    claude = ClaudeService()
                    parser = LocalizationGuidelinesParser(claude)
                    result = await parser.parse("test.md")

                    assert result is not None
                    assert result.source_file == "test.md"


class TestParserIntegration:
    """Integration tests for parsers."""

    @pytest.mark.asyncio
    async def test_brand_parser_full_workflow(self, brand_guidelines_text):
        """Test complete brand parsing workflow."""
        from src.genai.claude import ClaudeService
        from src.parsers.brand_parser import BrandGuidelinesParser

        extracted = {
            "source_file": "test.md",
            "primary_colors": ["#0066CC"],
            "primary_font": "Montserrat",
            "brand_voice": "Professional",
            "photography_style": "Modern minimalist",
        }

        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=brand_guidelines_text)):
                with patch("aiohttp.ClientSession.post") as mock_post:
                    mock_response = AsyncMock()
                    mock_response.status = 200
                    mock_response.json = AsyncMock(
                        return_value={
                            "content": [{"text": json.dumps(extracted)}],
                            "usage": {"input_tokens": 100, "output_tokens": 50},
                        }
                    )
                    mock_post.return_value.__aenter__.return_value = mock_response

                    claude = ClaudeService()
                    parser = BrandGuidelinesParser(claude)
                    result = await parser.parse("test.md")

                    assert result.primary_font == "Montserrat"
                    assert len(result.primary_colors) > 0

    @pytest.mark.asyncio
    async def test_localization_parser_full_workflow(self, localization_rules_yaml):
        """Test complete localization parsing workflow."""
        from src.genai.claude import ClaudeService
        from src.parsers.localization_parser import LocalizationGuidelinesParser

        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=localization_rules_yaml)):
                parser = LocalizationGuidelinesParser(ClaudeService())
                result = await parser.parse("test.yaml")

                assert result is not None
                assert len(result.market_specific_rules) >= 2
                assert "prohibited_terms" in result.model_dump()

    @pytest.mark.asyncio
    async def test_parser_error_handling(self):
        """Test parser error handling for invalid files."""
        from src.parsers.brand_parser import BrandGuidelinesParser

        parser = BrandGuidelinesParser(None)

        # File doesn't exist - should raise FileNotFoundError
        with pytest.raises(FileNotFoundError):
            await parser.parse("nonexistent_file.pdf")

    @pytest.mark.asyncio
    async def test_parser_handles_empty_file(self):
        """Test parser handles empty guideline files."""
        from src.genai.claude import ClaudeService
        from src.parsers.brand_parser import BrandGuidelinesParser

        extracted = {
            "source_file": "empty.md",
            "primary_colors": [],
            "primary_font": "Arial",
            "brand_voice": "Professional",
        }

        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="")):
                with patch("aiohttp.ClientSession.post") as mock_post:
                    mock_response = AsyncMock()
                    mock_response.status = 200
                    mock_response.json = AsyncMock(
                        return_value={
                            "content": [{"text": json.dumps(extracted)}],
                            "usage": {"input_tokens": 10, "output_tokens": 20},
                        }
                    )
                    mock_post.return_value.__aenter__.return_value = mock_response

                    claude = ClaudeService()
                    parser = BrandGuidelinesParser(claude)
                    result = await parser.parse("empty.md")

                    # Should return minimal guidelines
                    assert result is not None
                    assert result.source_file == "empty.md"
