"""Webhook endpoints for scraper to LEADS integration."""
from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ..pipelines.ingestion import IngestionPipeline
from ..pipelines.validation import ValidationPipeline
from ..pipelines.enrichment import EnrichmentPipeline
from ..pipelines.scoring import ScoringPipeline
from ..pipelines.categorization import CategorizationPipeline
from ..models.lead import FrontendFormat
from ..utils.formatters import LeadFormatter
from ..utils.logger import get_logger
from ..config import settings

logger = get_logger(__name__)
webhook_router = APIRouter(prefix="/webhooks", tags=["webhooks"])

ingestion = IngestionPipeline()
validation = ValidationPipeline()
enrichment = EnrichmentPipeline()
scoring = ScoringPipeline()
categorization = CategorizationPipeline()

_processed_leads: Dict[str, Any] = {}


class ScraperWebhookPayload(BaseModel):
    source: str
    leads: List[Dict[str, Any]]
    batch_id: str = ""
    scraper_version: str = ""


@webhook_router.post("/scraper/leads")
async def receive_scraped_leads(payload: ScraperWebhookPayload):
    """Receive batch of leads from a scraper."""
    logger.info(
        f"Webhook received {len(payload.leads)} leads from {payload.source}"
    )

    results = []
    for raw_lead in payload.leads:
        raw_lead["source"] = payload.source
        try:
            lead = ingestion.ingest(raw_lead)
            lead, validation_result = validation.validate(lead)

            if not validation_result["is_valid"] and validation_result["blocked_reasons"]:
                results.append({
                    "id": lead.id,
                    "status": "blocked",
                    "reasons": validation_result["blocked_reasons"],
                })
                continue

            lead = enrichment.enrich(lead)
            lead = scoring.score(lead)
            lead = categorization.categorize(lead)

            lead_dict = lead.model_dump()
            frontend_data = LeadFormatter.format_lead_for_frontend(lead_dict)
            lead.frontend = FrontendFormat(**frontend_data)

            _processed_leads[lead.id] = lead

            if lead.category == "hot":
                _notify_hot_lead(lead)

            results.append({
                "id": lead.id,
                "status": "processed",
                "category": lead.category,
                "score": lead.scores.overall_score,
                "company_name": lead.company.name,
            })
        except Exception as e:
            logger.error(f"Error processing lead: {e}")
            results.append({"status": "error", "error": str(e)})

    return {
        "batch_id": payload.batch_id,
        "processed": len([r for r in results if r.get("status") == "processed"]),
        "blocked": len([r for r in results if r.get("status") == "blocked"]),
        "errors": len([r for r in results if r.get("status") == "error"]),
        "results": results,
    }


@webhook_router.post("/lead/{lead_id}/email-opened")
async def email_opened(lead_id: str):
    """Track when a lead opens an email."""
    lead = _processed_leads.get(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    from datetime import datetime
    lead.outreach.initial_email_opened = True
    lead.outreach.initial_email_opened_at = datetime.utcnow()
    logger.info(f"Email opened by lead {lead_id}")
    return {"status": "tracked", "lead_id": lead_id}


@webhook_router.post("/lead/{lead_id}/email-clicked")
async def email_clicked(lead_id: str, link: str = ""):
    """Track when a lead clicks an email link."""
    lead = _processed_leads.get(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    lead.outreach.initial_email_clicked = True
    lead.outreach.clicked_link = link
    logger.info(f"Email link clicked by lead {lead_id}: {link}")
    return {"status": "tracked", "lead_id": lead_id, "link": link}


def _notify_hot_lead(lead) -> None:
    """Send Slack notification for hot lead."""
    if not settings.slack_webhook_url:
        return
    try:
        import httpx
        message = {
            "text": (
                f"HOT LEAD ALERT\n"
                f"Company: {lead.company.name}\n"
                f"Score: {lead.scores.overall_score}/100\n"
                f"Contact: {lead.primary_contact.name or 'Unknown'}\n"
                f"Phone: {lead.company.phone or 'N/A'}\n"
                f"Email: {lead.primary_contact.email or 'N/A'}"
            )
        }
        with httpx.Client(timeout=5.0) as client:
            client.post(settings.slack_webhook_url, json=message)
    except Exception as e:
        logger.warning(f"Slack notification failed: {e}")
