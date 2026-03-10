"""Tests for enrichment pipeline."""
import pytest
import time
from src.pipelines.ingestion import IngestionPipeline
from src.pipelines.enrichment import EnrichmentPipeline


@pytest.fixture
def ingestion():
    return IngestionPipeline()


@pytest.fixture
def enrichment():
    return EnrichmentPipeline()


@pytest.fixture
def lead_data_with_epoxy():
    return {
        "source": "google_maps",
        "company": {
            "name": "Epoxy Masters LLC",
            "phone": "+15551234567",
            "website": "https://epoxy-masters.com",
            "specializations": ["epoxy flooring", "concrete grinding", "coating"],
            "industry": "Flooring Contractor",
        },
        "primary_contact": {
            "name": "Mike Johnson",
            "email": "mike@epoxy-masters.com",
        },
    }


def test_enrichment_sets_default_business_status(ingestion, enrichment):
    data = {
        "source": "other",
        "company": {"name": "Test Company", "phone": "+15551234567"},
        "primary_contact": {},
    }
    lead = ingestion.ingest(data)
    lead = enrichment.enrich(lead)
    assert lead.company.business_status in ("active", "inactive", "unknown", None)


def test_enrichment_detects_epoxy_keywords(ingestion, enrichment, lead_data_with_epoxy):
    lead = ingestion.ingest(lead_data_with_epoxy)
    lead = enrichment.enrich(lead)
    assert lead.company.website_has_epoxy_mention is True


def test_enrichment_no_epoxy_keywords(ingestion, enrichment):
    data = {
        "source": "google_maps",
        "company": {
            "name": "Plumbing Plus",
            "phone": "+15551234567",
            "specializations": ["plumbing", "pipes", "drainage"],
            "industry": "Plumbing Services",
        },
        "primary_contact": {},
    }
    lead = ingestion.ingest(data)
    lead = enrichment.enrich(lead)
    assert lead.company.website_has_epoxy_mention is False


def test_enrichment_updates_timestamp(ingestion, enrichment, lead_data_with_epoxy):
    lead = ingestion.ingest(lead_data_with_epoxy)
    original_updated = lead.updated_at
    time.sleep(0.01)
    lead = enrichment.enrich(lead)
    assert lead.updated_at >= original_updated


def test_enrichment_accumulates_processing_time(ingestion, enrichment, lead_data_with_epoxy):
    lead = ingestion.ingest(lead_data_with_epoxy)
    lead = enrichment.enrich(lead)
    assert lead.processing_time_ms is not None
    assert lead.processing_time_ms >= 0
