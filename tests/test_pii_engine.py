"""
PII Engine test suite — 12 test cases covering Indian-context PII patterns
and the SESSION_PII_MAP reversibility mechanism.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest

from sentinel.session_pii_map import SessionPIIMap
from sentinel.pii_engine import PIIRedactionEngine
from sentinel.pii_restorer import PIIRestorer


@pytest.fixture
def pii_map():
    return SessionPIIMap()


@pytest.fixture
def engine(pii_map):
    return PIIRedactionEngine(pii_map)


@pytest.fixture
def restorer(pii_map):
    return PIIRestorer(pii_map)


# ── Tier 1 Regex Tests ────────────────────────────────────────────────────────

class TestAadhaarDetection:
    def test_spaced_format(self, engine):
        result = engine.redact("My Aadhaar is 2345 6789 0123")
        assert "2345 6789 0123" not in result.sanitised_text
        assert "[PII_AADHAAR_1]" in result.sanitised_text
        assert result.n_entities >= 1

    def test_entity_type(self, pii_map, engine):
        engine.redact("Aadhaar: 3456 7890 1234")
        placeholders = pii_map.get_placeholders()
        assert any("AADHAAR" in k for k in placeholders)


class TestPANDetection:
    def test_standard_format(self, engine):
        result = engine.redact("PAN card number ABCDE1234F")
        assert "ABCDE1234F" not in result.sanitised_text
        assert "[PII_PAN_1]" in result.sanitised_text

    def test_embedded_in_sentence(self, engine):
        result = engine.redact("Please provide FGHIJ5678K for tax filing")
        assert "FGHIJ5678K" not in result.sanitised_text


class TestIndianPhoneDetection:
    def test_with_country_code(self, engine):
        result = engine.redact("Call me at +91 98765 43210")
        assert "9876543210" not in result.sanitised_text
        assert result.n_entities >= 1

    def test_ten_digit_format(self, engine):
        result = engine.redact("My number is 9876543210")
        assert "9876543210" not in result.sanitised_text

    def test_mobile_starting_with_7(self, engine):
        result = engine.redact("Reach me at 7890123456")
        assert "7890123456" not in result.sanitised_text


class TestEmailDetection:
    def test_standard_email(self, engine):
        result = engine.redact("Send it to rajesh@gmail.com please")
        assert "rajesh@gmail.com" not in result.sanitised_text
        assert "[PII_EMAIL_1]" in result.sanitised_text

    def test_corporate_email(self, engine):
        result = engine.redact("CC: tanmay.vasishta@bmsce.ac.in")
        assert "@bmsce.ac.in" not in result.sanitised_text


# ── SESSION_PII_MAP Reversibility Tests ───────────────────────────────────────

class TestSessionPIIMap:
    def test_add_and_restore(self, pii_map):
        ph = pii_map.add("PERSON", "Rajesh Kumar")
        assert ph == "[PII_PERSON_1]"
        restored = pii_map.restore(f"Hello {ph}, your order is ready.")
        assert "Rajesh Kumar" in restored
        assert "[PII_PERSON_1]" not in restored

    def test_deduplication(self, pii_map):
        ph1 = pii_map.add("EMAIL", "test@example.com")
        ph2 = pii_map.add("EMAIL", "test@example.com")
        assert ph1 == ph2  # same value → same placeholder

    def test_multiple_types(self, pii_map):
        ph_person = pii_map.add("PERSON", "Arjun")
        ph_email = pii_map.add("EMAIL", "arjun@test.com")
        assert "PERSON" in ph_person
        assert "EMAIL" in ph_email

    def test_clear_resets_map(self, pii_map):
        pii_map.add("PERSON", "Sita")
        pii_map.clear()
        assert len(pii_map) == 0

    def test_counter_increments(self, pii_map):
        ph1 = pii_map.add("PERSON", "Rahul")
        ph2 = pii_map.add("PERSON", "Priya")
        assert ph1 == "[PII_PERSON_1]"
        assert ph2 == "[PII_PERSON_2]"


# ── Full Redact-Restore Round-Trip ────────────────────────────────────────────

class TestRoundTrip:
    def test_email_round_trip(self, pii_map, engine, restorer):
        original = "Please email kumar@gmail.com the results"
        result = engine.redact(original)
        assert "kumar@gmail.com" not in result.sanitised_text
        # Simulate response with placeholder
        fake_response = f"I will send the results to {list(pii_map.get_placeholders())[0]}"
        restored, warnings = restorer.restore_and_validate(fake_response)
        assert "kumar@gmail.com" in restored

    def test_aadhaar_not_in_cloud_payload(self, engine):
        result = engine.redact("Aadhaar is 2234 5678 9012 for Meera")
        # The sanitised text must not contain the Aadhaar number
        assert "2234 5678 9012" not in result.sanitised_text
        # Must contain a placeholder instead
        assert "[PII_AADHAAR_1]" in result.sanitised_text

    def test_multiple_entities_in_one_query(self, engine):
        text = "Email rajesh@gmail.com or call 9876543210 about PAN ABCDE1234F"
        result = engine.redact(text)
        assert "rajesh@gmail.com" not in result.sanitised_text
        assert "9876543210" not in result.sanitised_text
        assert "ABCDE1234F" not in result.sanitised_text
        assert result.n_entities >= 3


# ── PIIRestorer Unknown Placeholder Detection ─────────────────────────────────

class TestPIIRestorer:
    def test_unknown_placeholder_warning(self, pii_map, restorer):
        # Don't add anything to the map
        response = "Hello [PII_PERSON_99], your request is processed."
        _, warnings = restorer.restore_and_validate(response)
        assert any("Unknown placeholder" in w for w in warnings)

    def test_clean_response_no_warnings(self, pii_map, restorer):
        pii_map.add("EMAIL", "test@example.com")
        response = "The task is done."
        _, warnings = restorer.restore_and_validate(response)
        # No placeholder-related warnings on a clean response
        placeholder_warnings = [w for w in warnings if "Unknown placeholder" in w]
        assert len(placeholder_warnings) == 0
