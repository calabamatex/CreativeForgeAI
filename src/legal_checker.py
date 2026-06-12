"""Legal compliance checking for campaign content."""

import re
from dataclasses import dataclass

from src.models import CampaignMessage, LegalComplianceGuidelines


@dataclass
class ComplianceViolation:
    """Represents a legal compliance violation."""

    severity: str  # "error", "warning", "info"
    category: str  # "prohibited_word", "prohibited_claim", "missing_disclaimer", etc.
    field: str  # "headline", "subheadline", "cta", "product_description"
    violation: str  # The actual violation found
    message: str  # Human-readable description
    suggestion: str | None = None  # Suggested fix


class LegalComplianceChecker:
    """Validates campaign content against legal compliance guidelines."""

    def __init__(self, guidelines: LegalComplianceGuidelines):
        """
        Initialize checker with legal guidelines.

        Args:
            guidelines: Legal compliance guidelines to check against
        """
        self.guidelines = guidelines
        self.violations: list[ComplianceViolation] = []

    def check_content(
        self, message: CampaignMessage, product_content: dict[str, str] | None = None, locale: str = "en-US"
    ) -> tuple[bool, list[ComplianceViolation]]:
        """
        Check campaign content for legal compliance violations.

        Args:
            message: Campaign message to check
            product_content: Optional dict with product descriptions and features
            locale: Target locale for locale-specific checks

        Returns:
            Tuple of (is_compliant, list_of_violations)
        """
        self.violations = []

        # Check campaign message
        self._check_text(message.headline, "headline")
        self._check_text(message.subheadline, "subheadline")
        self._check_text(message.cta, "cta")

        # Check product content if provided
        if product_content:
            if "description" in product_content:
                self._check_text(product_content["description"], "product_description")
            if "features" in product_content:
                for i, feature in enumerate(product_content["features"]):
                    self._check_text(feature, f"product_feature_{i + 1}")

        # Check locale-specific restrictions
        if locale in self.guidelines.locale_restrictions:
            self._check_locale_specific(message, locale)

        # Check for required disclaimers
        self._check_disclaimers(message, product_content)

        # Check for superlatives if prohibited
        if self.guidelines.prohibit_superlatives:
            self._check_superlatives(message)

        # Determine if compliant (no "error" severity violations)
        is_compliant = all(v.severity != "error" for v in self.violations)

        return is_compliant, self.violations

    def _check_text(self, text: str, field: str) -> None:
        """Check a text field for violations."""
        if not text:
            return

        text_lower = text.lower()

        # Check prohibited words
        for word in self.guidelines.prohibited_words:
            if self._word_exists(word.lower(), text_lower):
                self.violations.append(
                    ComplianceViolation(
                        severity="error",
                        category="prohibited_word",
                        field=field,
                        violation=word,
                        message=f"Prohibited word '{word}' found in {field}",
                        suggestion=f"Remove or replace '{word}'",
                    )
                )

        # Check prohibited phrases
        for phrase in self.guidelines.prohibited_phrases:
            if phrase.lower() in text_lower:
                self.violations.append(
                    ComplianceViolation(
                        severity="error",
                        category="prohibited_phrase",
                        field=field,
                        violation=phrase,
                        message=f"Prohibited phrase '{phrase}' found in {field}",
                        suggestion=f"Remove or rephrase '{phrase}'",
                    )
                )

        # Check prohibited claims
        for claim in self.guidelines.prohibited_claims:
            if claim.lower() in text_lower:
                self.violations.append(
                    ComplianceViolation(
                        severity="error",
                        category="prohibited_claim",
                        field=field,
                        violation=claim,
                        message=f"Prohibited claim '{claim}' found in {field}",
                        suggestion="Remove unsubstantiated claim",
                    )
                )

        # Check restricted terms
        for term, contexts in self.guidelines.restricted_terms.items():
            if self._word_exists(term.lower(), text_lower):
                # Check if used in prohibited context
                for prohibited_context in contexts:
                    if prohibited_context.lower() in text_lower:
                        self.violations.append(
                            ComplianceViolation(
                                severity="warning",
                                category="restricted_term",
                                field=field,
                                violation=f"{term} with {prohibited_context}",
                                message=f"Restricted term '{term}' used with '{prohibited_context}' in {field}",
                                suggestion=f"Add disclaimer or remove '{prohibited_context}'",
                            )
                        )

        # Check protected trademarks
        for trademark in self.guidelines.protected_trademarks:
            if self._word_exists(trademark.lower(), text_lower):
                self.violations.append(
                    ComplianceViolation(
                        severity="error",
                        category="trademark_violation",
                        field=field,
                        violation=trademark,
                        message=f"Protected trademark '{trademark}' found in {field}",
                        suggestion=f"Remove competitor trademark '{trademark}'",
                    )
                )

    def _word_exists(self, word: str, text: str) -> bool:
        """Check if a word exists as a whole word (not as part of another word)."""
        # Use word boundaries to match whole words only
        pattern = r"\b" + re.escape(word) + r"\b"
        return bool(re.search(pattern, text, re.IGNORECASE))

    def _check_locale_specific(self, message: CampaignMessage, locale: str) -> None:
        """Check locale-specific restrictions."""
        locale_rules = self.guidelines.locale_restrictions.get(locale, {})

        if "prohibited_words" in locale_rules:
            text_lower = f"{message.headline} {message.subheadline} {message.cta}".lower()
            for word in locale_rules["prohibited_words"]:
                if self._word_exists(word.lower(), text_lower):
                    self.violations.append(
                        ComplianceViolation(
                            severity="error",
                            category="locale_prohibited_word",
                            field="message",
                            violation=word,
                            message=f"Word '{word}' prohibited in locale {locale}",
                            suggestion=f"Remove '{word}' for {locale} market",
                        )
                    )

    def _check_disclaimers(self, message: CampaignMessage, product_content: dict[str, str] | None) -> None:
        """Check if required disclaimers are present."""
        if not self.guidelines.required_disclaimers:
            return

        # For now, flag as warning that disclaimers may be needed
        for category, disclaimer_text in self.guidelines.required_disclaimers.items():
            self.violations.append(
                ComplianceViolation(
                    severity="info",
                    category="required_disclaimer",
                    field="campaign",
                    violation=category,
                    message=f"Required disclaimer for category '{category}': {disclaimer_text}",
                    suggestion="Ensure disclaimer is included in final materials",
                )
            )

    def _check_superlatives(self, message: CampaignMessage) -> None:
        """Check for prohibited superlatives."""
        superlatives = [
            "best",
            "perfect",
            "ultimate",
            "greatest",
            "finest",
            "optimal",
            "supreme",
            "unbeatable",
            "unsurpassed",
            "number one",
            "#1",
            "top",
            "leading",
        ]

        text_lower = f"{message.headline} {message.subheadline} {message.cta}".lower()

        for superlative in superlatives:
            if self._word_exists(superlative, text_lower):
                self.violations.append(
                    ComplianceViolation(
                        severity="warning",
                        category="superlative",
                        field="message",
                        violation=superlative,
                        message=f"Superlative '{superlative}' may require substantiation",
                        suggestion=f"Replace '{superlative}' with verifiable claim or add substantiation",
                    )
                )

    def generate_report(self) -> str:
        """Generate a human-readable compliance report."""
        if not self.violations:
            return "✅ No legal compliance violations found."

        report = ["⚠️  Legal Compliance Report", "=" * 50, ""]

        # Group by severity
        errors = [v for v in self.violations if v.severity == "error"]
        warnings = [v for v in self.violations if v.severity == "warning"]
        info = [v for v in self.violations if v.severity == "info"]

        if errors:
            report.append(f"🚨 ERRORS ({len(errors)}) - Must be fixed:")
            report.append("-" * 50)
            for v in errors:
                report.append(f"  • [{v.field}] {v.message}")
                if v.suggestion:
                    report.append(f"    💡 {v.suggestion}")
                report.append("")

        if warnings:
            report.append(f"⚠️  WARNINGS ({len(warnings)}) - Review recommended:")
            report.append("-" * 50)
            for v in warnings:
                report.append(f"  • [{v.field}] {v.message}")
                if v.suggestion:
                    report.append(f"    💡 {v.suggestion}")
                report.append("")

        if info:
            report.append(f"ℹ️  INFO ({len(info)}) - For your information:")
            report.append("-" * 50)
            for v in info:
                report.append(f"  • [{v.field}] {v.message}")
                if v.suggestion:
                    report.append(f"    💡 {v.suggestion}")
                report.append("")

        # Summary
        report.append("=" * 50)
        report.append(f"Total: {len(errors)} errors, {len(warnings)} warnings, {len(info)} info")

        return "\n".join(report)

    def get_violation_summary(self) -> dict[str, int]:
        """Get a summary count of violations by severity."""
        return {
            "errors": sum(1 for v in self.violations if v.severity == "error"),
            "warnings": sum(1 for v in self.violations if v.severity == "warning"),
            "info": sum(1 for v in self.violations if v.severity == "info"),
            "total": len(self.violations),
        }
