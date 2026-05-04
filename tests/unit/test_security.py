"""Tests for security utilities."""
import pytest
from pathlib import Path

from src.security import (
    sanitize_prompt,
    validate_upload_extension,
    validate_upload_size,
    validate_safe_path,
    is_valid_uuid,
    MAX_PROMPT_LENGTH,
    MAX_UPLOAD_SIZE_BYTES,
    ALLOWED_UPLOAD_EXTENSIONS,
)


class TestSanitizePrompt:
    """Test prompt sanitization."""

    def test_normal_text_unchanged(self):
        assert sanitize_prompt("Generate a product photo") == "Generate a product photo"

    def test_empty_string(self):
        assert sanitize_prompt("") == ""

    def test_strips_control_characters(self):
        result = sanitize_prompt("hello\x00world\x07test")
        assert "\x00" not in result
        assert "\x07" not in result
        assert "helloworld" in result

    def test_preserves_tabs_and_newlines(self):
        result = sanitize_prompt("line1\nline2\tindented")
        assert "\n" in result
        assert "\t" in result

    def test_truncates_long_prompts(self):
        long_prompt = "x" * (MAX_PROMPT_LENGTH + 500)
        result = sanitize_prompt(long_prompt)
        assert len(result) <= MAX_PROMPT_LENGTH

    def test_custom_max_length(self):
        result = sanitize_prompt("a" * 100, max_length=50)
        assert len(result) == 50

    def test_unicode_normalization(self):
        # NFC normalization: e + combining accent -> single char
        result = sanitize_prompt("caf\u0065\u0301")
        assert result == "caf\u00e9"

    def test_strips_whitespace(self):
        assert sanitize_prompt("  hello  ") == "hello"


class TestValidateUploadExtension:
    """Test upload extension validation."""

    @pytest.mark.parametrize("filename,expected_ext", [
        ("doc.pdf", ".pdf"),
        ("file.docx", ".docx"),
        ("data.json", ".json"),
        ("config.yaml", ".yaml"),
        ("config.yml", ".yml"),
        ("readme.txt", ".txt"),
    ])
    def test_allowed_extensions(self, filename, expected_ext):
        assert validate_upload_extension(filename) == expected_ext

    @pytest.mark.parametrize("filename", [
        "script.py",
        "program.exe",
        "image.png",
        "style.css",
    ])
    def test_disallowed_extensions(self, filename):
        with pytest.raises(ValueError, match="not allowed"):
            validate_upload_extension(filename)

    def test_empty_filename(self):
        with pytest.raises(ValueError, match="must not be empty"):
            validate_upload_extension("")

    def test_case_insensitive(self):
        assert validate_upload_extension("FILE.PDF") == ".pdf"


class TestValidateUploadSize:
    """Test upload size validation."""

    def test_within_limit(self):
        validate_upload_size(1024)  # 1 KB — no exception

    def test_at_limit(self):
        validate_upload_size(MAX_UPLOAD_SIZE_BYTES)  # exactly at limit

    def test_exceeds_limit(self):
        with pytest.raises(ValueError, match="exceeds maximum"):
            validate_upload_size(MAX_UPLOAD_SIZE_BYTES + 1)


class TestValidateSafePath:
    """Test path traversal protection."""

    def test_safe_path(self, tmp_path):
        (tmp_path / "data").mkdir()
        result = validate_safe_path("data", tmp_path)
        assert result == (tmp_path / "data").resolve()

    def test_rejects_dot_dot(self, tmp_path):
        with pytest.raises(ValueError, match="must not contain"):
            validate_safe_path("../etc/passwd", tmp_path)

    def test_rejects_escaping_path(self, tmp_path):
        with pytest.raises(ValueError, match="must not contain"):
            validate_safe_path("../../outside", tmp_path)

    def test_empty_path(self, tmp_path):
        with pytest.raises(ValueError, match="must not be empty"):
            validate_safe_path("", tmp_path)

    def test_nested_safe_path(self, tmp_path):
        nested = tmp_path / "a" / "b"
        nested.mkdir(parents=True)
        result = validate_safe_path("a/b", tmp_path)
        assert str(tmp_path.resolve()) in str(result)


class TestIsValidUUID:
    """Test UUID validation."""

    def test_valid_uuid(self):
        assert is_valid_uuid("550e8400-e29b-41d4-a716-446655440000") is True

    def test_invalid_uuid_too_short(self):
        assert is_valid_uuid("550e8400-e29b") is False

    def test_invalid_uuid_bad_chars(self):
        assert is_valid_uuid("not-a-uuid-at-all-nope-nope-nopeno") is False

    def test_empty_string(self):
        assert is_valid_uuid("") is False
