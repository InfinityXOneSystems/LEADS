"""Tests for XPS Intelligence sync service and sync API endpoints."""
import json
import pytest
from unittest.mock import MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.services.xps_sync import XPSSyncService, EXPORT_SCHEMA_VERSION
from src.pipelines.ingestion import IngestionPipeline
from src.pipelines.validation import ValidationPipeline
from src.pipelines.enrichment import EnrichmentPipeline
from src.pipelines.scoring import ScoringPipeline
from src.pipelines.categorization import CategorizationPipeline
from src.models.lead import FrontendFormat
from src.utils.formatters import LeadFormatter


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_lead():
    """Build a fully processed Lead object ready for export."""
    raw = {
        "source": "google_maps",
        "company": {
            "name": "Epoxy Masters LLC",
            "phone": "+15551112222",
            "address": "10 Commerce Blvd",
            "city": "Cleveland",
            "state": "OH",
            "zip": "44101",
            "website": "https://epoxymasters.com",
            "industry": "Epoxy Flooring",
            "business_status": "active",
            "specializations": ["epoxy floors", "polished concrete"],
            "google_rating": 4.7,
            "google_reviews_count": 85,
        },
        "primary_contact": {
            "name": "Alice Builder",
            "title": "Owner",
            "email": "alice@epoxymasters.com",
            "phone": "+15551112222",
        },
    }
    ingestion = IngestionPipeline()
    validation = ValidationPipeline()
    enrichment = EnrichmentPipeline()
    scoring = ScoringPipeline()
    categorization = CategorizationPipeline()

    lead = ingestion.ingest(raw)
    lead, _ = validation.validate(lead)
    lead = enrichment.enrich(lead)
    lead = scoring.score(lead)
    lead = categorization.categorize(lead)
    lead_dict = lead.model_dump()
    lead.frontend = FrontendFormat(**LeadFormatter.format_lead_for_frontend(lead_dict))
    return lead


@pytest.fixture
def sync_service():
    return XPSSyncService(
        github_token="",  # no token – dispatch calls are mocked
        xps_system_repo="InfinityXOneSystems/LEADS",
        xps_frontend_repo="InfinityXOneSystems/frontend-system",
        pages_branch="gh-pages",
    )


@pytest.fixture
def sync_client():
    from src.api.sync import sync_router
    app = FastAPI(title="Sync Test")
    app.include_router(sync_router)
    return TestClient(app)


# ---------------------------------------------------------------------------
# XPSSyncService unit tests
# ---------------------------------------------------------------------------

class TestXPSSyncService:
    def test_build_export_payload_structure(self, sync_service, sample_lead):
        payload = sync_service.build_export_payload([sample_lead])

        assert payload["schema_version"] == EXPORT_SCHEMA_VERSION
        assert "exported_at" in payload
        assert "source_repo" in payload
        assert "totals" in payload
        assert "leads" in payload
        assert "hot" in payload
        assert "warm" in payload
        assert "cold" in payload

    def test_build_export_payload_totals(self, sync_service, sample_lead):
        payload = sync_service.build_export_payload([sample_lead])
        totals = payload["totals"]

        assert totals["all"] == 1
        assert totals["hot"] + totals["warm"] + totals["cold"] == 1

    def test_build_export_payload_lead_fields(self, sync_service, sample_lead):
        payload = sync_service.build_export_payload([sample_lead])
        lead = payload["leads"][0]

        assert "id" in lead
        assert "source" in lead
        assert "category" in lead
        assert "overall_score" in lead
        assert "company" in lead
        assert "contact" in lead
        assert "display" in lead
        assert "created_at" in lead

        assert lead["company"]["name"] == "Epoxy Masters LLC"
        assert lead["contact"]["name"] == "Alice Builder"

    def test_category_filtering(self, sync_service, sample_lead):
        payload = sync_service.build_export_payload([sample_lead])
        category = sample_lead.category

        assert len(payload[category]) == 1
        for other in {"hot", "warm", "cold"} - {category}:
            assert len(payload[other]) == 0

    def test_export_to_json_is_valid_json(self, sync_service, sample_lead):
        payload = sync_service.build_export_payload([sample_lead])
        json_str = XPSSyncService.export_to_json(payload)
        parsed = json.loads(json_str)
        assert parsed["schema_version"] == EXPORT_SCHEMA_VERSION

    def test_empty_lead_list(self, sync_service):
        payload = sync_service.build_export_payload([])
        assert payload["totals"]["all"] == 0
        assert payload["leads"] == []

    def test_dispatch_returns_no_token_when_unset(self, sync_service):
        payload = sync_service.build_export_payload([])
        result = sync_service.dispatch_frontend_update(payload)
        assert result["success"] is False
        assert result["reason"] == "no_token"

    def test_dispatch_with_token_sends_correct_request(self, sync_service, sample_lead):
        sync_service.github_token = "ghp_test_token"
        payload = sync_service.build_export_payload([sample_lead])

        mock_response = MagicMock()
        mock_response.status_code = 204

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value = mock_client

            result = sync_service.dispatch_frontend_update(payload)

        assert result["success"] is True
        assert result["status_code"] == 204
        # Reset token so other tests aren't affected
        sync_service.github_token = ""

    def test_sync_updates_status(self, sync_service, sample_lead):
        initial = sync_service.get_status()
        assert initial["last_sync_at"] is None

        sync_service.sync([sample_lead])

        updated = sync_service.get_status()
        assert updated["last_sync_at"] is not None
        assert updated["last_sync_status"] in ("ok", "partial")

    def test_get_status_returns_counts(self, sync_service, sample_lead):
        sync_service.sync([sample_lead])
        status = sync_service.get_status()
        assert "last_sync_counts" in status
        assert status["last_sync_counts"]["all"] == 1

    def test_serialize_lead_from_dict(self, sync_service):
        lead_dict = {
            "id": "abc-123",
            "source": "manual",
            "category": "warm",
            "category_rank": 1,
            "scores": {"overall_score": 60, "buying_likelihood": 0.6, "confidence": 0.8},
            "tags": ["epoxy-potential"],
            "company": {"name": "Test Co"},
            "primary_contact": {"name": "Test User", "email": "t@test.com"},
            "frontend": {"display_name": "Test Co", "key_facts": []},
        }
        result = XPSSyncService._serialize_lead(lead_dict)
        assert result["id"] == "abc-123"
        assert result["category"] == "warm"
        assert result["overall_score"] == 60
        assert result["company"]["name"] == "Test Co"


# ---------------------------------------------------------------------------
# Sync API endpoint tests
# ---------------------------------------------------------------------------

class TestSyncRouter:
    def test_sync_status_initially_empty(self, sync_client):
        response = sync_client.get("/api/v1/sync/status")
        assert response.status_code == 200
        data = response.json()
        assert data["last_sync_at"] is None
        assert data["last_sync_status"] == "never"

    def test_trigger_sync_without_leads_returns_400(self, sync_client):
        response = sync_client.post("/api/v1/sync/trigger")
        assert response.status_code == 400

    def test_push_and_sync_processes_leads(self, sync_client):
        payload = {
            "source": "google_maps",
            "batch_id": "test-batch-sync-001",
            "leads": [
                {
                    "source": "google_maps",
                    "company": {
                        "name": "Sync Test Co",
                        "phone": "+15553339999",
                        "address": "1 Test Ave",
                        "city": "Columbus",
                        "state": "OH",
                        "business_status": "active",
                        "specializations": ["epoxy floors"],
                    },
                    "primary_contact": {
                        "name": "Test Owner",
                        "email": "owner@synctest.com",
                    },
                }
            ],
        }
        response = sync_client.post("/api/v1/sync/push", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "processed" in data
        assert "sync" in data
        assert data["batch_id"] == "test-batch-sync-001"

    def test_export_leads_all(self, sync_client):
        # First push a lead so the store is non-empty
        sync_client.post(
            "/api/v1/sync/push",
            json={
                "source": "yelp",
                "leads": [
                    {
                        "company": {
                            "name": "Export Test Co",
                            "phone": "+15554445555",
                        },
                        "primary_contact": {},
                    }
                ],
            },
        )
        response = sync_client.get("/api/v1/sync/export")
        assert response.status_code == 200
        data = response.json()
        assert "schema_version" in data
        assert "totals" in data
        assert "leads" in data

    def test_export_leads_filtered_category(self, sync_client):
        for category in ("hot", "warm", "cold"):
            response = sync_client.get(f"/api/v1/sync/export?category={category}")
            assert response.status_code == 200
            data = response.json()
            assert data["category"] == category
            assert "leads" in data

    def test_export_invalid_category_rejected(self, sync_client):
        response = sync_client.get("/api/v1/sync/export?category=unknown")
        assert response.status_code == 422
