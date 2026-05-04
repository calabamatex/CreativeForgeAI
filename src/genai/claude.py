"""Claude API service for guideline extraction and localization."""
import aiohttp
import json
import asyncio
from typing import Dict, Any, Optional
import structlog
from src.config import get_config
from src.models import ComprehensiveBrandGuidelines, LocalizationGuidelines, CampaignMessage
from src.security import sanitize_prompt

logger = structlog.get_logger(__name__)


class ClaudeService:
    """Service for interacting with Anthropic Claude API."""

    def __init__(self, api_key: Optional[str] = None, max_retries: int = 3):
        config = get_config()
        self.api_key = api_key or config.CLAUDE_API_KEY

        if not self.api_key:
            raise ValueError(
                "CLAUDE_API_KEY is required. Set it in environment variables or pass to constructor."
            )

        self.api_url = config.CLAUDE_API_URL
        self.max_retries = max_retries
        self.model = "claude-sonnet-4-20250514"
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(
                total=120,
                connect=10,
                sock_read=60,
            )
            connector = aiohttp.TCPConnector(
                limit=20,
                limit_per_host=10,
                ttl_dns_cache=300,
                enable_cleanup_closed=True,
            )
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
            )
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
    
    async def extract_brand_guidelines(
        self,
        text_content: str,
        source_file: str
    ) -> ComprehensiveBrandGuidelines:
        """Extract brand guidelines from document text using Claude."""
        prompt = f"""Extract brand guidelines from the following document and return as JSON:

Document:
{text_content[:10000]}

Extract and return JSON with these fields:
- primary_colors: list of hex colors
- secondary_colors: list of hex colors (optional)
- primary_font: string
- secondary_font: string (optional)
- brand_voice: string describing tone and voice
- photography_style: string describing photography guidelines
- logo_clearspace: integer (pixels)
- logo_min_size: integer (pixels)
- prohibited_uses: list of strings
- prohibited_elements: list of strings
- approved_taglines: list of strings

Return ONLY valid JSON, no additional text."""
        
        response_text = await self._call_claude(prompt)
        
        try:
            # Parse JSON response
            data = json.loads(response_text)
            data['source_file'] = source_file
            return ComprehensiveBrandGuidelines(**data)
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback with defaults
            return ComprehensiveBrandGuidelines(
                source_file=source_file,
                primary_colors=["#000000"],
                primary_font="Arial",
                brand_voice="Professional",
                photography_style="Modern"
            )
    
    async def extract_localization_guidelines(
        self,
        text_content: str,
        source_file: str
    ) -> LocalizationGuidelines:
        """Extract localization guidelines from document text."""
        prompt = f"""Extract localization guidelines from the following document and return as JSON:

Document:
{text_content[:10000]}

Extract and return JSON with these fields:
- supported_locales: list of locale codes (e.g., ["en-US", "es-MX"])
- market_specific_rules: dict with locale keys containing market rules
- prohibited_terms: dict with locale keys containing lists of prohibited terms
- translation_glossary: dict with locale keys containing term translations
- tone_guidelines: dict with locale keys containing tone descriptions
- cultural_considerations: dict with locale keys containing cultural notes

Return ONLY valid JSON."""
        
        response_text = await self._call_claude(prompt)
        
        try:
            data = json.loads(response_text)
            data['source_file'] = source_file
            return LocalizationGuidelines(**data)
        except (json.JSONDecodeError, ValueError):
            return LocalizationGuidelines(
                source_file=source_file,
                supported_locales=["en-US"],
                market_specific_rules={},
                prohibited_terms={},
                translation_glossary={}
            )
    
    async def localize_message(
        self,
        original_message: CampaignMessage,
        target_locale: str,
        localization_guidelines: Optional[LocalizationGuidelines] = None
    ) -> CampaignMessage:
        """Generate localized campaign message for target locale."""

        # Build context from guidelines
        context = ""
        if localization_guidelines and target_locale in localization_guidelines.market_specific_rules:
            rules = localization_guidelines.market_specific_rules[target_locale]
            context += f"\nMarket Rules: {json.dumps(rules)}"

        if localization_guidelines and target_locale in localization_guidelines.prohibited_terms:
            prohibited = localization_guidelines.prohibited_terms[target_locale]
            context += f"\nProhibited Terms: {', '.join(prohibited)}"

        if localization_guidelines and target_locale in localization_guidelines.translation_glossary:
            glossary = localization_guidelines.translation_glossary[target_locale]
            context += f"\nTranslation Glossary: {json.dumps(glossary)}"

        prompt = f"""Localize the following campaign message to {target_locale}:

Original Message:
- Headline: {original_message.headline}
- Subheadline: {original_message.subheadline}
- CTA: {original_message.cta}

{context}

Return ONLY JSON with fields: headline, subheadline, cta
Make it culturally appropriate and engaging for {target_locale} market."""

        response_text = await self._call_claude(prompt)

        try:
            # Try to extract JSON from response (Claude might wrap it in markdown)
            if '```json' in response_text:
                # Extract JSON from markdown code block
                start = response_text.find('```json') + 7
                end = response_text.find('```', start)
                response_text = response_text[start:end].strip()
            elif '```' in response_text:
                # Generic code block
                start = response_text.find('```') + 3
                end = response_text.find('```', start)
                response_text = response_text[start:end].strip()

            data = json.loads(response_text)
            return CampaignMessage(
                locale=target_locale,
                headline=data.get('headline', original_message.headline),
                subheadline=data.get('subheadline', original_message.subheadline),
                cta=data.get('cta', original_message.cta)
            )
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("claude.localization_failed", locale=target_locale, error=str(e), response_preview=response_text[:200])
            return CampaignMessage(
                locale=target_locale,
                headline=original_message.headline,
                subheadline=original_message.subheadline,
                cta=original_message.cta
            )
    
    async def _call_claude(self, prompt: str) -> str:
        """Make API call to Claude with retry logic.

        The prompt is sanitized (control characters stripped, length capped)
        before being sent to the API.
        """
        prompt = sanitize_prompt(prompt, max_length=16_000)  # Claude can handle longer context
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}]
        }
        
        for attempt in range(self.max_retries):
            try:
                session = await self._get_session()
                async with session.post(
                    self.api_url,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        try:
                            return data["content"][0]["text"]
                        except (KeyError, IndexError, TypeError) as e:
                            raise ValueError(f"Unexpected Claude API response format: {e}")
                    elif response.status == 429:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    else:
                        error_text = await response.text()
                        logger.warning("claude.api_error", status=response.status, error=error_text)
                        if attempt < self.max_retries - 1:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        raise Exception(f"Claude API error: {response.status}")
            except asyncio.TimeoutError:
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise
        
        raise Exception("Max retries exceeded for Claude API")
