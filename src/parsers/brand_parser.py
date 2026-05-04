"""Parser for brand guidelines documents."""
import fitz  # PyMuPDF
import docx
import re
from pathlib import Path
from typing import List
import structlog
from src.genai.claude import ClaudeService
from src.models import ComprehensiveBrandGuidelines

logger = structlog.get_logger(__name__)


class BrandGuidelinesParser:
    """Parse brand guidelines from various document formats."""
    
    def __init__(self, claude_service: ClaudeService = None):
        self.claude_service = claude_service or ClaudeService()
    
    async def parse(self, file_path: str) -> ComprehensiveBrandGuidelines:
        """Parse brand guidelines from file."""
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Extract text based on format
        if path.suffix.lower() == '.pdf':
            text = self._extract_pdf(file_path)
        elif path.suffix.lower() in ['.docx', '.doc']:
            text = self._extract_docx(file_path)
        else:
            # Plain text
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()

        # Try Claude first, fall back to regex if it fails
        try:
            return await self.claude_service.extract_brand_guidelines(text, file_path)
        except Exception as e:
            logger.warning("brand_parser.claude_extraction_failed", error=str(e), fallback="regex")
            return self._extract_with_regex(text, file_path)
    
    def _extract_pdf(self, file_path: str) -> str:
        """Extract text from PDF using PyMuPDF."""
        text = ""
        with fitz.open(file_path) as doc:
            for page in doc:
                text += page.get_text()
        return text
    
    def _extract_docx(self, file_path: str) -> str:
        """Extract text from DOCX using python-docx."""
        doc = docx.Document(file_path)
        return "\n".join([para.text for para in doc.paragraphs])

    def _extract_with_regex(self, text: str, source_file: str) -> ComprehensiveBrandGuidelines:
        """Fallback: Extract basic brand guidelines using regex patterns."""
        # Extract hex colors
        colors = re.findall(r'#[0-9A-Fa-f]{6}', text)
        primary_colors = colors[:3] if colors else ["#000000"]
        secondary_colors = colors[3:6] if len(colors) > 3 else []

        # Extract font names (common patterns)
        font_patterns = [
            r'(?:Primary Font|Font|Typography):\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:font|typeface)',
        ]
        fonts = []
        for pattern in font_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            fonts.extend(matches)

        primary_font = fonts[0] if fonts else "Arial"
        secondary_font = fonts[1] if len(fonts) > 1 else None

        # Extract brand voice (simple heuristic)
        voice_keywords = ['professional', 'casual', 'friendly', 'innovative', 'modern', 'traditional']
        brand_voice = next((kw for kw in voice_keywords if kw.lower() in text.lower()), "Professional")

        # Extract photography style keywords
        photo_keywords = ['modern', 'minimalist', 'clean', 'natural', 'professional']
        found_styles = [kw for kw in photo_keywords if kw.lower() in text.lower()]
        photography_style = ", ".join(found_styles) if found_styles else "Modern"

        return ComprehensiveBrandGuidelines(
            source_file=source_file,
            primary_colors=primary_colors,
            secondary_colors=secondary_colors,
            primary_font=primary_font,
            secondary_font=secondary_font,
            brand_voice=brand_voice.capitalize(),
            photography_style=photography_style.capitalize()
        )
