"""Parser for localization guidelines."""

import json
from pathlib import Path

import yaml

from src.models import LocalizationGuidelines
from src.parsers.brand_parser import BrandGuidelinesParser


class LocalizationGuidelinesParser(BrandGuidelinesParser):
    """Parse localization guidelines from various formats."""

    async def parse(self, file_path: str) -> LocalizationGuidelines:
        """Parse localization guidelines from file."""
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Handle structured formats directly
        if path.suffix.lower() in [".yaml", ".yml"]:
            with open(file_path) as f:
                data = yaml.safe_load(f)
                data["source_file"] = file_path
                return LocalizationGuidelines(**data)

        elif path.suffix.lower() == ".json":
            with open(file_path) as f:
                data = json.load(f)
                data["source_file"] = file_path
                return LocalizationGuidelines(**data)

        # For documents, extract text and use Claude
        else:
            if path.suffix.lower() == ".pdf":
                text = self._extract_pdf(file_path)
            elif path.suffix.lower() in [".docx", ".doc"]:
                text = self._extract_docx(file_path)
            else:
                with open(file_path, encoding="utf-8") as f:
                    text = f.read()

            return await self.claude_service.extract_localization_guidelines(text, file_path)
