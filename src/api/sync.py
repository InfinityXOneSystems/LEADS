"""Sync API router – trigger XPS Intelligence sync and check status."""
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..models.lead import FrontendFormat
from ..pipelines.ingestion import IngestionPipeline
from ..pipelines.validation import ValidationPipeline
from ..pipelines.enrichment import EnrichmentPipeline
from ..pipelines.scoring import ScoringPipeline
from ..pipelines.categorization import CategorizationPipeline
from ..services.xps_sync import XPSSyncService
from ..utils.formatters import LeadFormatter
from ..utils.logger import get_logger
from ..config import settings

logger = get_logger(__name__)
sync_router = APIRouter(prefix="/api/v1/sync", tags=["sync"])

_ingestion = IngestionPipeline()
_validation = ValidationPipeline()
_enrichment = EnrichmentPipeline()
_scoring = ScoringPipeline()
_categorization = CategorizationPipeline()

_sync_service = XPSSyncService(
    github_token=settings.xps_github_token,
    xps_system_repo=settings.xps_system_repo,
    xps_frontend_repo=settings.xps_frontend_repo,
    pages_branch=settings.xps_pages_branch,
)

# In-memory lead store shared with the sync router.
# In production this would be replaced by a database query.
_synced_leads: Dict[str, Any] = {}


class SyncLeadsRequest(BaseModel):
    """Request body for pushing a batch of leads and triggering a sync."""
    source: str = "other"
    leads: List[Dict[str, Any]]
    batch_id: str = ""


def _process_lead(raw: Dict[str, Any]) -> Any:
    """Run the full pipeline and return the processed Lead object."""
    lead = _ingestion.ingest(raw)
    lead, validation_result = _validation.validate(lead)
    if not validation_result.get("is_valid") and validation_result.get(
        "blocked_reasons"
    ):
        return None
    lead = _enrichment.enrich(lead)
    lead = _scoring.score(lead)
    lead = _categorization.categorize(lead)
    lead_dict = lead.model_dump()
    frontend_data = LeadFormatter.format_lead_for_frontend(lead_dict)
    lead.frontend = FrontendFormat(**frontend_data)
    return lead


@sync_router.post("/push", response_model=Dict[str, Any])
async def push_and_sync(request: SyncLeadsRequest):
    """Ingest a batch of leads, normalize them, then push to XPS systems.

    This is the primary entry point for all scrapers: data arrives here,
    gets normalized through the full pipeline, and is immediately propagated
    to the XPS Intelligence GitHub Pages and the XPS Intelligence Frontend.
    """
    processed = []
    skipped = 0
    errors = 0

    for raw in request.leads:
        raw["source"] = request.source
        try:
            lead = _process_lead(raw)
            if lead is None:
                skipped += 1
                continue
            _synced_leads[lead.id] = lead
            processed.append(lead)
        except Exception as exc:
            logger.error(f"Error processing lead during push: {exc}")
            errors += 1

    sync_result = _sync_service.sync(list(_synced_leads.values()))

    return {
        "batch_id": request.batch_id,
        "processed": len(processed),
        "skipped": skipped,
        "errors": errors,
        "sync": sync_result,
    }


@sync_router.post("/trigger", response_model=Dict[str, Any])
async def trigger_sync():
    """Trigger an immediate sync of all in-memory leads to XPS systems.

    Dispatches a ``leads-updated`` repository_dispatch event to the
    XPS Intelligence Frontend repo so that GitHub Pages are rebuilt.
    """
    if not _synced_leads:
        raise HTTPException(
            status_code=400,
            detail="No leads available to sync. Use POST /api/v1/sync/push first.",
        )

    result = _sync_service.sync(list(_synced_leads.values()))
    return result


@sync_router.get("/status", response_model=Dict[str, Any])
async def sync_status():
    """Return the status of the most recent XPS sync operation."""
    status = _sync_service.get_status()
    status["total_leads_in_memory"] = len(_synced_leads)
    return status


@sync_router.get("/export", response_model=Dict[str, Any])
async def export_leads(
    category: str = Query(
        "all",
        pattern="^(all|hot|warm|cold)$",
        description="Filter by category: all | hot | warm | cold",
    )
):
    """Return the normalized export payload consumed by GitHub Pages / frontend.

    The ``category`` query parameter narrows the result set.
    """
    leads = list(_synced_leads.values())
    payload = _sync_service.build_export_payload(leads)

    if category != "all":
        return {
            "schema_version": payload["schema_version"],
            "exported_at": payload["exported_at"],
            "source_repo": payload["source_repo"],
            "totals": payload["totals"],
            "leads": payload.get(category, []),
            "category": category,
        }

    return payload
