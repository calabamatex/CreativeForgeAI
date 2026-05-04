"""Tests for LegalComplianceChecker logic."""
import pytest

from src.legal_checker import LegalComplianceChecker, ComplianceViolation
from src.models import LegalComplianceGuidelines, CampaignMessage


@pytest.fixture
def basic_guidelines():
    """Minimal legal guidelines for testing."""
    return LegalComplianceGuidelines(
        source_file="test.yaml",
        prohibited_words=["guarantee", "free"],
        prohibited_phrases=["no risk", "100% safe"],
        prohibited_claims=["clinically proven", "guaranteed results"],
        restricted_terms={"premium": ["cheap", "budget"]},
        protected_trademarks=["CompetitorBrand"],
        required_disclaimers={"financial": "Past performance does not guarantee future results"},
        prohibit_superlatives=True,
        locale_restrictions={
            "de-DE": {"prohibited_words": ["verboten"]},
        },
    )


@pytest.fixture
def clean_message():
    """Campaign message with no violations."""
    return CampaignMessage(
        headline="Discover Our New Product",
        subheadline="Quality you can trust",
        cta="Learn More",
        locale="en-US",
    )


@pytest.fixture
def violating_message():
    """Campaign message with multiple violations."""
    return CampaignMessage(
        headline="Free guarantee on the best product",
        subheadline="Clinically proven, no risk involved",
        cta="Get CompetitorBrand quality",
        locale="en-US",
    )


class TestCheckContent:
    """Test the main check_content method."""

    def test_clean_message_passes(self, basic_guidelines, clean_message):
        checker = LegalComplianceChecker(basic_guidelines)
        is_compliant, violations = checker.check_content(clean_message)

        # Should be compliant (only info-level disclaimer reminders)
        assert is_compliant is True
        error_violations = [v for v in violations if v.severity == "error"]
        assert len(error_violations) == 0

    def test_violating_message_fails(self, basic_guidelines, violating_message):
        checker = LegalComplianceChecker(basic_guidelines)
        is_compliant, violations = checker.check_content(violating_message)

        assert is_compliant is False
        error_violations = [v for v in violations if v.severity == "error"]
        assert len(error_violations) > 0


class TestProhibitedWords:
    """Test prohibited word detection."""

    def test_detects_prohibited_word_in_headline(self, basic_guidelines):
        msg = CampaignMessage(
            headline="Get it for free today",
            subheadline="Great value",
            cta="Shop Now",
            locale="en-US",
        )
        checker = LegalComplianceChecker(basic_guidelines)
        _, violations = checker.check_content(msg)

        word_violations = [v for v in violations if v.category == "prohibited_word"]
        assert any(v.violation == "free" for v in word_violations)

    def test_whole_word_matching(self, basic_guidelines):
        """'free' should not match 'freedom'."""
        msg = CampaignMessage(
            headline="Experience freedom",
            subheadline="No limits",
            cta="Join",
            locale="en-US",
        )
        checker = LegalComplianceChecker(basic_guidelines)
        _, violations = checker.check_content(msg)

        word_violations = [v for v in violations if v.category == "prohibited_word"]
        assert not any(v.violation == "free" for v in word_violations)


class TestProhibitedClaims:
    """Test prohibited claim detection."""

    def test_detects_prohibited_claim(self, basic_guidelines):
        msg = CampaignMessage(
            headline="Clinically proven results",
            subheadline="Trust the science",
            cta="Try Now",
            locale="en-US",
        )
        checker = LegalComplianceChecker(basic_guidelines)
        _, violations = checker.check_content(msg)

        claim_violations = [v for v in violations if v.category == "prohibited_claim"]
        assert len(claim_violations) > 0


class TestProhibitedPhrases:
    """Test prohibited phrase detection."""

    def test_detects_prohibited_phrase(self, basic_guidelines):
        msg = CampaignMessage(
            headline="No risk investment",
            subheadline="Safe and sound",
            cta="Invest",
            locale="en-US",
        )
        checker = LegalComplianceChecker(basic_guidelines)
        _, violations = checker.check_content(msg)

        phrase_violations = [v for v in violations if v.category == "prohibited_phrase"]
        assert any(v.violation == "no risk" for v in phrase_violations)


class TestTrademarks:
    """Test trademark detection."""

    def test_detects_competitor_trademark(self, basic_guidelines):
        msg = CampaignMessage(
            headline="Better than CompetitorBrand",
            subheadline="Switch today",
            cta="Compare",
            locale="en-US",
        )
        checker = LegalComplianceChecker(basic_guidelines)
        _, violations = checker.check_content(msg)

        tm_violations = [v for v in violations if v.category == "trademark_violation"]
        assert len(tm_violations) > 0


class TestSuperlatives:
    """Test superlative detection."""

    def test_detects_superlatives(self, basic_guidelines):
        msg = CampaignMessage(
            headline="The best product ever",
            subheadline="Perfect for everyone",
            cta="Buy the ultimate solution",
            locale="en-US",
        )
        checker = LegalComplianceChecker(basic_guidelines)
        _, violations = checker.check_content(msg)

        sup_violations = [v for v in violations if v.category == "superlative"]
        superlatives_found = {v.violation for v in sup_violations}
        assert "best" in superlatives_found
        assert "perfect" in superlatives_found
        assert "ultimate" in superlatives_found

    def test_no_superlative_check_when_disabled(self):
        guidelines = LegalComplianceGuidelines(
            source_file="test.yaml",
            prohibit_superlatives=False,
        )
        msg = CampaignMessage(
            headline="The best product ever",
            subheadline="Perfect",
            cta="Buy",
            locale="en-US",
        )
        checker = LegalComplianceChecker(guidelines)
        _, violations = checker.check_content(msg)

        sup_violations = [v for v in violations if v.category == "superlative"]
        assert len(sup_violations) == 0


class TestLocaleSpecific:
    """Test locale-specific rules."""

    def test_locale_prohibited_words(self, basic_guidelines):
        msg = CampaignMessage(
            headline="Das ist verboten content",
            subheadline="German market",
            cta="Kaufen",
            locale="de-DE",
        )
        checker = LegalComplianceChecker(basic_guidelines)
        _, violations = checker.check_content(msg, locale="de-DE")

        locale_violations = [v for v in violations if v.category == "locale_prohibited_word"]
        assert len(locale_violations) > 0


class TestDisclaimers:
    """Test required disclaimer checks."""

    def test_disclaimer_info_violations(self, basic_guidelines, clean_message):
        checker = LegalComplianceChecker(basic_guidelines)
        _, violations = checker.check_content(clean_message)

        disclaimer_violations = [v for v in violations if v.category == "required_disclaimer"]
        assert len(disclaimer_violations) == 1
        assert disclaimer_violations[0].severity == "info"
        assert "financial" in disclaimer_violations[0].violation


class TestProductContent:
    """Test product-level content checking."""

    def test_checks_product_description(self, basic_guidelines):
        msg = CampaignMessage(
            headline="Our Product",
            subheadline="Great quality",
            cta="Buy",
            locale="en-US",
        )
        product_content = {
            "description": "This free product is guaranteed to work",
            "features": ["Clinically proven effectiveness"],
        }
        checker = LegalComplianceChecker(basic_guidelines)
        is_compliant, violations = checker.check_content(
            msg, product_content=product_content
        )

        assert is_compliant is False
        fields = {v.field for v in violations if v.severity == "error"}
        assert "product_description" in fields or "product_feature_1" in fields


class TestRestrictedTerms:
    """Test restricted term context detection."""

    def test_restricted_term_in_prohibited_context(self, basic_guidelines):
        msg = CampaignMessage(
            headline="Premium quality at a cheap price",
            subheadline="Affordable",
            cta="Buy",
            locale="en-US",
        )
        checker = LegalComplianceChecker(basic_guidelines)
        _, violations = checker.check_content(msg)

        restricted = [v for v in violations if v.category == "restricted_term"]
        assert len(restricted) > 0


class TestReport:
    """Test report generation."""

    def test_clean_report(self, basic_guidelines, clean_message):
        checker = LegalComplianceChecker(basic_guidelines)
        checker.check_content(clean_message)

        # Has info violations (disclaimers) but no errors
        report = checker.generate_report()
        assert "Legal Compliance Report" in report

    def test_no_violations_report(self):
        guidelines = LegalComplianceGuidelines(source_file="test.yaml")
        msg = CampaignMessage(
            headline="Hello", subheadline="World", cta="Click", locale="en-US"
        )
        checker = LegalComplianceChecker(guidelines)
        checker.check_content(msg)
        report = checker.generate_report()
        assert "No legal compliance violations found" in report

    def test_report_with_errors(self, basic_guidelines, violating_message):
        checker = LegalComplianceChecker(basic_guidelines)
        checker.check_content(violating_message)
        report = checker.generate_report()

        assert "ERRORS" in report
        assert "Must be fixed" in report


class TestViolationSummary:
    """Test violation summary counts."""

    def test_summary_counts(self, basic_guidelines, violating_message):
        checker = LegalComplianceChecker(basic_guidelines)
        checker.check_content(violating_message)
        summary = checker.get_violation_summary()

        assert "errors" in summary
        assert "warnings" in summary
        assert "info" in summary
        assert "total" in summary
        assert summary["total"] == summary["errors"] + summary["warnings"] + summary["info"]
        assert summary["errors"] > 0

    def test_empty_summary(self):
        guidelines = LegalComplianceGuidelines(source_file="test.yaml")
        msg = CampaignMessage(
            headline="Hello", subheadline="World", cta="Click", locale="en-US"
        )
        checker = LegalComplianceChecker(guidelines)
        checker.check_content(msg)
        summary = checker.get_violation_summary()

        assert summary["total"] == 0
        assert summary["errors"] == 0
