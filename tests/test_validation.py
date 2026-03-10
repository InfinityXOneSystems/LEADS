"""Tests for validation pipeline."""
import pytest
from src.pipelines.ingestion import IngestionPipeline
from src.pipelines.validation import ValidationPipeline
from src.utils.validators import PhoneValidator, EmailValidator, AddressValidator


@pytest.fixture
def ingestion():
    return IngestionPipeline()


@pytest.fixture
def validation():
    return ValidationPipeline()


@pytest.fixture
def valid_lead_data():
    return {
        "source": "google_maps",
        "company": {
            "name": "Acme Concrete Solutions",
            "phone": "+15551234567",
            "address": "123 Main St",
            "city": "Cleveland",
            "state": "OH",
            "zip": "44101",
            "website": "https://acme-concrete.com",
            "industry": "Concrete Contractors",
            "business_status": "active",
        },
        "primary_contact": {
            "name": "John Smith",
            "title": "Owner",
            "email": "john@acme-concrete.com",
            "phone": "+15551234567",
        },
    }


def test_valid_lead_passes_validation(ingestion, validation, valid_lead_data):
    lead = ingestion.ingest(valid_lead_data)
    _, result = validation.validate(lead)
    assert result["is_valid"] is True
    assert len(result["blocked_reasons"]) == 0


def test_missing_company_name_fails_validation(ingestion, validation):
    data = {
        "source": "google_maps",
        "company": {"name": "", "phone": "+15551234567"},
        "primary_contact": {"email": "test@test.com"},
    }
    lead = ingestion.ingest(data)
    _, result = validation.validate(lead)
    assert result["is_valid"] is False
    assert any("company_name" in issue for issue in result["issues"])


def test_invalid_phone_fails_validation(ingestion, validation):
    data = {
        "source": "google_maps",
        "company": {"name": "Test Co", "phone": "not-a-phone"},
        "primary_contact": {"email": "test@test.com", "phone": "not-a-phone"},
    }
    lead = ingestion.ingest(data)
    _, result = validation.validate(lead)
    assert result["is_valid"] is False


def test_excluded_industry_is_blocked(ingestion, validation):
    data = {
        "source": "google_maps",
        "company": {
            "name": "John's Hobby",
            "phone": "+15551234567",
            "industry": "personal hobby project",
        },
        "primary_contact": {"email": "john@example.com"},
    }
    lead = ingestion.ingest(data)
    _, result = validation.validate(lead)
    assert "excluded_industry" in result["blocked_reasons"]


def test_completeness_score_calculation(ingestion, validation, valid_lead_data):
    lead = ingestion.ingest(valid_lead_data)
    _, result = validation.validate(lead)
    assert result["completeness_score"] > 0.5


def test_phone_validator_valid():
    assert PhoneValidator.is_valid("+15551234567") is True
    assert PhoneValidator.is_valid("555-123-4567") is True
    assert PhoneValidator.is_valid("(555) 123-4567") is True


def test_phone_validator_invalid():
    assert PhoneValidator.is_valid("") is False
    assert PhoneValidator.is_valid("123") is False
    assert PhoneValidator.is_valid("not-a-phone") is False


def test_phone_to_display():
    result = PhoneValidator.to_display("+15551234567")
    assert result == "+1 (555) 123-4567"


def test_phone_to_tel_link():
    result = PhoneValidator.to_tel_link("+15551234567")
    assert result == "tel:+15551234567"


def test_email_validator_valid():
    assert EmailValidator.is_valid("john@example.com") is True
    assert EmailValidator.is_valid("john.smith+tag@company.co.uk") is True


def test_email_validator_invalid():
    assert EmailValidator.is_valid("") is False
    assert EmailValidator.is_valid("not-an-email") is False
    assert EmailValidator.is_valid("@nodomain.com") is False


def test_email_to_mailto_link():
    result = EmailValidator.to_mailto_link("john@example.com")
    assert result == "mailto:john@example.com"


def test_address_validator_valid():
    assert AddressValidator.is_valid("123 Main St") is True
    assert AddressValidator.is_valid("456 Oak Ave, Suite 100") is True


def test_address_validator_invalid():
    assert AddressValidator.is_valid("") is False
    assert AddressValidator.is_valid("x") is False
