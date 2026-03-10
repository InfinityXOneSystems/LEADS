"""Tests for API routes."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app():
    from fastapi import FastAPI
    from src.api.routes import router
    from src.api.webhooks import webhook_router
    application = FastAPI(title="LEADS API Test")
    application.include_router(router)
    application.include_router(webhook_router)
    return application


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def sample_lead_payload():
    return {
        "source": "google_maps",
        "company": {
            "name": "Test Concrete Co",
            "phone": "+15551234567",
            "address": "123 Test St",
            "city": "Cleveland",
            "state": "OH",
            "zip": "44101",
            "website": "https://test-concrete.com",
            "industry": "Concrete Contractor",
            "business_status": "active",
            "specializations": ["epoxy floors", "polished concrete"],
            "google_rating": 4.5,
            "google_reviews_count": 50,
        },
        "primary_contact": {
            "name": "Bob Builder",
            "title": "Owner",
            "email": "bob@test-concrete.com",
            "phone": "+15551234567",
        },
    }


def test_ingest_lead(client, sample_lead_payload):
    response = client.post("/api/v1/leads/ingest", json=sample_lead_payload)
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["status"] == "ingested"
    assert data["company_name"] == "Test Concrete Co"


def test_validate_lead(client, sample_lead_payload):
    response = client.post("/api/v1/leads/validate", json=sample_lead_payload)
    assert response.status_code == 200
    data = response.json()
    assert "is_valid" in data
    assert "issues" in data
    assert "warnings" in data


def test_score_lead(client, sample_lead_payload):
    response = client.post("/api/v1/leads/score", json=sample_lead_payload)
    assert response.status_code == 200
    data = response.json()
    assert "overall_score" in data
    assert "category" in data
    assert 0 <= data["overall_score"] <= 100


def test_process_full_pipeline(client, sample_lead_payload):
    response = client.post("/api/v1/leads/process", json=sample_lead_payload)
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert "overall_score" in data
    assert "category" in data
    assert data["category"] in ("hot", "warm", "cold")


def test_get_hot_leads_empty(client):
    response = client.get("/api/v1/leads/hot")
    assert response.status_code == 200
    data = response.json()
    assert "leads" in data
    assert "total" in data
    assert data["category"] == "hot"


def test_get_warm_leads_empty(client):
    response = client.get("/api/v1/leads/warm")
    assert response.status_code == 200


def test_get_cold_leads_empty(client):
    response = client.get("/api/v1/leads/cold")
    assert response.status_code == 200


def test_get_lead_not_found(client):
    response = client.get("/api/v1/leads/nonexistent-id-12345")
    assert response.status_code == 404


def test_search_leads(client, sample_lead_payload):
    client.post("/api/v1/leads/process", json=sample_lead_payload)
    response = client.get("/api/v1/leads/search?query=Test+Concrete")
    assert response.status_code == 200
    data = response.json()
    assert "leads" in data


def test_webhook_receive_leads(client, sample_lead_payload):
    payload = {
        "source": "google_maps",
        "leads": [sample_lead_payload],
        "batch_id": "test-batch-001",
    }
    response = client.post("/webhooks/scraper/leads", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "processed" in data
    assert data["processed"] >= 0


def test_send_email_lead_not_found(client):
    response = client.post(
        "/api/v1/leads/nonexistent-id/send-email?email_type=initial"
    )
    assert response.status_code == 404
