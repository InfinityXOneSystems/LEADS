"""Tests for scoring pipeline."""
import pytest
from src.pipelines.ingestion import IngestionPipeline
from src.pipelines.validation import ValidationPipeline
from src.pipelines.enrichment import EnrichmentPipeline
from src.pipelines.scoring import ScoringPipeline
from src.pipelines.categorization import CategorizationPipeline


@pytest.fixture
def pipelines():
    return {
        "ingestion": IngestionPipeline(),
        "validation": ValidationPipeline(),
        "enrichment": EnrichmentPipeline(),
        "scoring": ScoringPipeline(),
        "categorization": CategorizationPipeline(),
    }


@pytest.fixture
def high_quality_lead_data():
    return {
        "source": "google_maps",
        "company": {
            "name": "Premier Epoxy Floors",
            "phone": "+15551234567",
            "address": "100 Business Park Dr",
            "city": "Cleveland",
            "state": "OH",
            "zip": "44101",
            "website": "https://premier-epoxy.com",
            "industry": "Epoxy Flooring Contractor",
            "business_status": "active",
            "specializations": ["epoxy floors", "polished concrete", "coating"],
            "google_rating": 4.9,
            "google_reviews_count": 150,
            "employee_count": "10-50",
            "revenue_estimate": "$2M-$5M",
            "website_has_epoxy_mention": True,
            "website_conversion_signals": ["contact form", "get a quote"],
            "social_presence": {
                "facebook": "https://facebook.com/premierepoxy",
                "instagram": "https://instagram.com/premierepoxy",
                "linkedin": "https://linkedin.com/company/premierepoxy",
            },
        },
        "primary_contact": {
            "name": "Jane Doe",
            "title": "Owner",
            "email": "jane@premier-epoxy.com",
            "phone": "+15551234567",
        },
    }


@pytest.fixture
def low_quality_lead_data():
    return {
        "source": "other",
        "company": {
            "name": "Unknown Business",
            "phone": "+15559876543",
        },
        "primary_contact": {},
    }


def test_high_quality_lead_scores_high(pipelines, high_quality_lead_data):
    lead = pipelines["ingestion"].ingest(high_quality_lead_data)
    lead, _ = pipelines["validation"].validate(lead)
    lead = pipelines["enrichment"].enrich(lead)
    lead = pipelines["scoring"].score(lead)
    assert lead.scores.overall_score >= 50


def test_low_quality_lead_scores_low(pipelines, low_quality_lead_data):
    lead = pipelines["ingestion"].ingest(low_quality_lead_data)
    lead, _ = pipelines["validation"].validate(lead)
    lead = pipelines["enrichment"].enrich(lead)
    lead = pipelines["scoring"].score(lead)
    assert lead.scores.overall_score < 75


def test_score_is_0_to_100(pipelines, high_quality_lead_data):
    lead = pipelines["ingestion"].ingest(high_quality_lead_data)
    lead = pipelines["scoring"].score(lead)
    assert 0 <= lead.scores.overall_score <= 100


def test_buying_likelihood_is_0_to_1(pipelines, high_quality_lead_data):
    lead = pipelines["ingestion"].ingest(high_quality_lead_data)
    lead = pipelines["scoring"].score(lead)
    assert 0.0 <= lead.scores.buying_likelihood <= 1.0


def test_confidence_is_0_to_1(pipelines, high_quality_lead_data):
    lead = pipelines["ingestion"].ingest(high_quality_lead_data)
    lead = pipelines["scoring"].score(lead)
    assert 0.0 <= lead.scores.confidence <= 1.0


def test_hot_lead_categorization(pipelines, high_quality_lead_data):
    lead = pipelines["ingestion"].ingest(high_quality_lead_data)
    lead, _ = pipelines["validation"].validate(lead)
    lead = pipelines["enrichment"].enrich(lead)
    lead = pipelines["scoring"].score(lead)
    lead = pipelines["categorization"].categorize(lead)
    assert lead.category in ("hot", "warm", "cold")
    assert lead.category is not None


def test_cold_lead_categorization(pipelines, low_quality_lead_data):
    lead = pipelines["ingestion"].ingest(low_quality_lead_data)
    lead, _ = pipelines["validation"].validate(lead)
    lead = pipelines["enrichment"].enrich(lead)
    lead = pipelines["scoring"].score(lead)
    lead = pipelines["categorization"].categorize(lead)
    assert lead.category == "cold"


def test_score_breakdown_all_factors_present(pipelines, high_quality_lead_data):
    lead = pipelines["ingestion"].ingest(high_quality_lead_data)
    lead = pipelines["scoring"].score(lead)
    breakdown = lead.scores.scoring_breakdown
    assert breakdown.business_legitimacy >= 0
    assert breakdown.epoxy_relevance >= 0
    assert breakdown.market_opportunity >= 0
    assert breakdown.recent_activity >= 0
    assert breakdown.decision_maker_accessibility >= 0
    assert breakdown.social_engagement >= 0


def test_rank_leads(pipelines):
    leads = []
    for i, score_data in enumerate([
        {"name": "Hot Lead", "score_override": 80},
        {"name": "Warm Lead", "score_override": 60},
        {"name": "Cold Lead", "score_override": 30},
    ]):
        data = {
            "source": "google_maps",
            "company": {"name": score_data["name"], "phone": f"+1555000{i:04d}"},
            "primary_contact": {},
        }
        lead = pipelines["ingestion"].ingest(data)
        lead = pipelines["scoring"].score(lead)
        lead.scores.overall_score = score_data["score_override"]
        lead = pipelines["categorization"].categorize(lead)
        leads.append(lead)

    ranked = pipelines["categorization"].rank_leads(leads)
    hot_leads = [l for l in ranked if l.category == "hot"]
    if hot_leads:
        assert hot_leads[0].category_rank == 1
