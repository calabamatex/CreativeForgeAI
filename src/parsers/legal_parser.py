"""Parser for legal compliance guidelines."""
import yaml
import json
from pathlib import Path
import structlog
from src.models import LegalComplianceGuidelines
from src.parsers.brand_parser import BrandGuidelinesParser

logger = structlog.get_logger(__name__)


class LegalComplianceParser(BrandGuidelinesParser):
    """Parse legal compliance guidelines from various formats."""

    async def parse(self, file_path: str) -> LegalComplianceGuidelines:
        """Parse legal compliance guidelines from file."""
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Handle structured formats directly
        if path.suffix.lower() in ['.yaml', '.yml']:
            with open(file_path, 'r') as f:
                data = yaml.safe_load(f)
                data['source_file'] = file_path
                return LegalComplianceGuidelines(**data)

        elif path.suffix.lower() == '.json':
            with open(file_path, 'r') as f:
                data = json.load(f)
                data['source_file'] = file_path
                return LegalComplianceGuidelines(**data)

        # For documents, extract text and use Claude
        else:
            if path.suffix.lower() == '.pdf':
                text = self._extract_pdf(file_path)
            elif path.suffix.lower() in ['.docx', '.doc']:
                text = self._extract_docx(file_path)
            else:
                with open(file_path, 'r', encoding='utf-8') as f:
                    text = f.read()

            # For now, return empty guidelines if no structured format
            # In the future, could use Claude to extract legal guidelines from text
            logger.warning("legal_parser.unsupported_format", suffix=path.suffix, suggestion="Use YAML or JSON format")
            return LegalComplianceGuidelines(source_file=file_path)
