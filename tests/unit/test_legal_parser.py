"""Tests for the legal compliance guidelines parser."""
import pytest
import json
import yaml
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from src.parsers.legal_parser import LegalComplianceParser
from src.models import LegalComplianceGuidelines


@pytest.fixture
def mock_claude_service():
    service = MagicMock()
    service.extract_brand_guidelines = AsyncMock()
    return service


@pytest.fixture
def parser(mock_claude_service):
    return LegalComplianceParser(claude_service=mock_claude_service)


@pytest.fixture
def sample_guidelines_data():
    return {
        "prohibited_words": ["guarantee", "free"],
        "prohibited_phrases": ["no risk"],
        "prohibited_claims": ["clinically proven"],
        "required_disclaimers": {"health": "Consult your doctor"},
        "protected_trademarks": ["SomeBrand"],
        "prohibit_superlatives": True,
        "industry_regulations": ["FTC", "FDA"],
    }


class TestParseYAML:
    """Test parsing YAML legal guidelines."""

    @pytest.mark.asyncio
    async def test_parse_yaml(self, parser, tmp_path, sample_guidelines_data):
        yaml_file = tmp_path / "legal.yaml"
        yaml_file.write_text(yaml.dump(sample_guidelines_data))

        result = await parser.parse(str(yaml_file))

        assert isinstance(result, LegalComplianceGuidelines)
        assert result.prohibited_words == ["guarantee", "free"]
        assert result.prohibit_superlatives is True
        assert result.source_file == str(yaml_file)

    @pytest.mark.asyncio
    async def test_parse_yml_extension(self, parser, tmp_path, sample_guidelines_data):
        yml_file = tmp_path / "legal.yml"
        yml_file.write_text(yaml.dump(sample_guidelines_data))

        result = await parser.parse(str(yml_file))

        assert isinstance(result, LegalComplianceGuidelines)
        assert result.prohibited_words == ["guarantee", "free"]


class TestParseJSON:
    """Test parsing JSON legal guidelines."""

    @pytest.mark.asyncio
    async def test_parse_json(self, parser, tmp_path, sample_guidelines_data):
        json_file = tmp_path / "legal.json"
        json_file.write_text(json.dumps(sample_guidelines_data))

        result = await parser.parse(str(json_file))

        assert isinstance(result, LegalComplianceGuidelines)
        assert result.prohibited_claims == ["clinically proven"]
        assert result.source_file == str(json_file)

    @pytest.mark.asyncio
    async def test_parse_json_minimal(self, parser, tmp_path):
        json_file = tmp_path / "minimal.json"
        json_file.write_text(json.dumps({}))

        result = await parser.parse(str(json_file))

        assert isinstance(result, LegalComplianceGuidelines)
        assert result.prohibited_words == []
        assert result.prohibit_superlatives is False


class TestParseUnsupportedFormats:
    """Test fallback for unsupported formats."""

    @pytest.mark.asyncio
    async def test_plain_text_returns_empty_guidelines(self, parser, tmp_path):
        txt_file = tmp_path / "legal.txt"
        txt_file.write_text("No swearing in ads. Must include disclaimer.")

        result = await parser.parse(str(txt_file))

        assert isinstance(result, LegalComplianceGuidelines)
        assert result.source_file == str(txt_file)
        # Text files get empty guidelines (no structured extraction)
        assert result.prohibited_words == []


class TestFileNotFound:
    """Test error handling for missing files."""

    @pytest.mark.asyncio
    async def test_missing_file_raises(self, parser):
        with pytest.raises(FileNotFoundError):
            await parser.parse("/nonexistent/legal.yaml")


class TestGuidelinesFields:
    """Test that all fields roundtrip correctly through parsing."""

    @pytest.mark.asyncio
    async def test_all_fields_preserved(self, parser, tmp_path):
        data = {
            "prohibited_words": ["cure", "miracle"],
            "prohibited_phrases": ["100% safe", "no side effects"],
            "prohibited_claims": ["FDA approved"],
            "required_disclaimers": {"financial": "Past results..."},
            "restricted_terms": {"premium": ["cheap"]},
            "protected_trademarks": ["BrandX"],
            "age_restrictions": 21,
            "restricted_audiences": ["minors"],
            "restricted_regions": ["EU"],
            "industry_regulations": ["FTC"],
            "require_substantiation": True,
            "prohibit_superlatives": True,
            "locale_restrictions": {"de-DE": {"prohibited_words": ["verboten"]}},
        }
        json_file = tmp_path / "full.json"
        json_file.write_text(json.dumps(data))

        result = await parser.parse(str(json_file))

        assert result.prohibited_words == ["cure", "miracle"]
        assert result.age_restrictions == 21
        assert result.restricted_audiences == ["minors"]
        assert result.require_substantiation is True
        assert "de-DE" in result.locale_restrictions
