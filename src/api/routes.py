"""API routes for the LEADS system."""
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..models.lead import Lead, FrontendFormat
from ..pipelines.ingestion import IngestionPipeline
from ..pipelines.validation import ValidationPipeline
from ..pipelines.enrichment import EnrichmentPipeline
from ..pipelines.scoring import ScoringPipeline
from ..pipelines.categorization import CategorizationPipeline
from ..utils.formatters import LeadFormatter
from ..utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/leads", tags=["leads"])

_leads_store: Dict[str, Lead] = {}

ingestion_pipeline = IngestionPipeline()
validation_pipeline = ValidationPipeline()
enrichment_pipeline = EnrichmentPipeline()
scoring_pipeline = ScoringPipeline()
categorization_pipeline = CategorizationPipeline()


class IngestRequest(BaseModel):
    source: Optional[str] = "other"
    company: Dict[str, Any]
    primary_contact: Optional[Dict[str, Any]] = {}
    secondary_contacts: Optional[List[Dict[str, Any]]] = []


class LeadResponse(BaseModel):
    id: str
    source: Optional[str]
    company_name: str
    overall_score: int
    category: Optional[str]
    display_name: str
    display_phone: Optional[str]
    display_phone_link: Optional[str]
    display_email: Optional[str]
    display_email_link: Optional[str]
    avatar_url: Optional[str]
    description: Optional[str]
    key_facts: List[str]
    tags: List[str]
    category_rank: Optional[int]
    created_at: datetime


class PaginatedLeadsResponse(BaseModel):
    leads: List[LeadResponse]
    total: int
    page: int
    page_size: int
    category: Optional[str] = None


def _lead_to_response(lead: Lead) -> LeadResponse:
    frontend = lead.frontend
    return LeadResponse(
        id=lead.id,
        source=lead.source,
        company_name=lead.company.name,
        overall_score=lead.scores.overall_score,
        category=lead.category,
        display_name=frontend.display_name or lead.company.name,
        display_phone=frontend.display_phone,
        display_phone_link=frontend.display_phone_link,
        display_email=frontend.display_email,
        display_email_link=frontend.display_email_link,
        avatar_url=frontend.avatar_url,
        description=frontend.description,
        key_facts=frontend.key_facts,
        tags=lead.tags,
        category_rank=lead.category_rank,
        created_at=lead.created_at,
    )


def _run_full_pipeline(raw_data: dict) -> tuple:
    """Run the complete lead processing pipeline."""
    lead = ingestion_pipeline.ingest(raw_data)
    lead, validation_result = validation_pipeline.validate(lead)
    lead = enrichment_pipeline.enrich(lead)
    lead = scoring_pipeline.score(lead)
    lead = categorization_pipeline.categorize(lead)
    lead_dict = lead.model_dump()
    frontend_data = LeadFormatter.format_lead_for_frontend(lead_dict)
    lead.frontend = FrontendFormat(**frontend_data)
    return lead, validation_result


@router.post("/ingest", response_model=Dict[str, Any])
async def ingest_lead(request: IngestRequest):
    """Ingest a raw lead from a scraper."""
    raw_data = request.model_dump()
    lead = ingestion_pipeline.ingest(raw_data)
    _leads_store[lead.id] = lead
    return {"id": lead.id, "status": "ingested", "company_name": lead.company.name}


@router.post("/validate", response_model=Dict[str, Any])
async def validate_lead(lead_data: Dict[str, Any]):
    """Validate a lead object."""
    lead = ingestion_pipeline.ingest(lead_data)
    lead, result = validation_pipeline.validate(lead)
    return {"lead_id": lead.id, **result}


@router.post("/enrich", response_model=Dict[str, Any])
async def enrich_lead(lead_data: Dict[str, Any]):
    """Enrich a validated lead."""
    lead = ingestion_pipeline.ingest(lead_data)
    lead = enrichment_pipeline.enrich(lead)
    return {"lead_id": lead.id, "enriched": True,
            "company": lead.company.model_dump()}


@router.post("/score", response_model=Dict[str, Any])
async def score_lead(lead_data: Dict[str, Any]):
    """Score an enriched lead."""
    lead = ingestion_pipeline.ingest(lead_data)
    lead = scoring_pipeline.score(lead)
    lead = categorization_pipeline.categorize(lead)
    return {
        "lead_id": lead.id,
        "overall_score": lead.scores.overall_score,
        "category": lead.category,
        "buying_likelihood": lead.scores.buying_likelihood,
        "confidence": lead.scores.confidence,
        "breakdown": lead.scores.scoring_breakdown.model_dump(),
    }


@router.post("/process", response_model=Dict[str, Any])
async def process_lead(request: IngestRequest):
    """Full pipeline: ingest -> validate -> enrich -> score -> categorize."""
    raw_data = request.model_dump()
    lead, validation_result = _run_full_pipeline(raw_data)
    _leads_store[lead.id] = lead
    return {
        "id": lead.id,
        "company_name": lead.company.name,
        "overall_score": lead.scores.overall_score,
        "category": lead.category,
        "validation": validation_result,
        "frontend": lead.frontend.model_dump(),
    }


@router.get("/hot", response_model=PaginatedLeadsResponse)
async def get_hot_leads(page: int = Query(1, ge=1),
                         page_size: int = Query(50, ge=1, le=100)):
    """Get all hot leads (score 75+), sorted by score DESC."""
    hot = sorted(
        [l for l in _leads_store.values() if l.category == "hot"],
        key=lambda x: x.scores.overall_score, reverse=True
    )
    start = (page - 1) * page_size
    paginated = hot[start:start + page_size]
    return PaginatedLeadsResponse(
        leads=[_lead_to_response(l) for l in paginated],
        total=len(hot), page=page, page_size=page_size, category="hot"
    )


@router.get("/warm", response_model=PaginatedLeadsResponse)
async def get_warm_leads(page: int = Query(1, ge=1),
                          page_size: int = Query(50, ge=1, le=100)):
    """Get all warm leads (score 50-74)."""
    warm = sorted(
        [l for l in _leads_store.values() if l.category == "warm"],
        key=lambda x: x.scores.overall_score, reverse=True
    )
    start = (page - 1) * page_size
    paginated = warm[start:start + page_size]
    return PaginatedLeadsResponse(
        leads=[_lead_to_response(l) for l in paginated],
        total=len(warm), page=page, page_size=page_size, category="warm"
    )


@router.get("/cold", response_model=PaginatedLeadsResponse)
async def get_cold_leads(page: int = Query(1, ge=1),
                          page_size: int = Query(50, ge=1, le=100)):
    """Get all cold leads (score <50)."""
    cold = sorted(
        [l for l in _leads_store.values() if l.category == "cold"],
        key=lambda x: x.scores.overall_score, reverse=True
    )
    start = (page - 1) * page_size
    paginated = cold[start:start + page_size]
    return PaginatedLeadsResponse(
        leads=[_lead_to_response(l) for l in paginated],
        total=len(cold), page=page, page_size=page_size, category="cold"
    )


@router.get("/search", response_model=PaginatedLeadsResponse)
async def search_leads(query: str = Query(..., min_length=1),
                        page: int = Query(1, ge=1),
                        page_size: int = Query(50, ge=1, le=100)):
    """Search leads by company name, contact, city, etc."""
    q = query.lower()
    results = []
    for lead in _leads_store.values():
        if (q in lead.company.name.lower() or
                (lead.primary_contact.name and q in lead.primary_contact.name.lower()) or
                (lead.company.city and q in lead.company.city.lower()) or
                (lead.company.state and q in lead.company.state.lower()) or
                (lead.primary_contact.email and q in lead.primary_contact.email.lower())):
            results.append(lead)

    results.sort(key=lambda x: x.scores.overall_score, reverse=True)
    start = (page - 1) * page_size
    paginated = results[start:start + page_size]
    return PaginatedLeadsResponse(
        leads=[_lead_to_response(l) for l in paginated],
        total=len(results), page=page, page_size=page_size
    )


@router.get("/{lead_id}", response_model=Dict[str, Any])
async def get_lead(lead_id: str):
    """Get full lead object by ID."""
    lead = _leads_store.get(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead.model_dump()


@router.post("/{lead_id}/send-email", response_model=Dict[str, Any])
async def send_lead_email(lead_id: str,
                           email_type: str = Query("initial",
                                                    pattern="^(initial|follow_up|final)$")):
    """Send email to a lead."""
    lead = _leads_store.get(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    if not lead.primary_contact.email:
        raise HTTPException(status_code=400, detail="Lead has no email address")

    from ..services.email_outreach import EmailOutreachService
    from ..config import settings
    service = EmailOutreachService(
        smtp_host=settings.smtp_host,
        smtp_port=settings.smtp_port,
        smtp_user=settings.smtp_user,
        smtp_password=settings.smtp_password,
        from_email=settings.from_email,
        from_name=settings.from_name,
        frontend_url=settings.frontend_url,
    )

    if email_type == "initial":
        result = service.send_initial_email(
            lead_id=lead.id,
            to_email=lead.primary_contact.email,
            decision_maker_name=lead.primary_contact.name or "",
            company_name=lead.company.name,
            specializations=lead.company.specializations,
        )
        if result.get("success"):
            lead.outreach.initial_email_sent = True
            lead.outreach.initial_email_sent_at = datetime.utcnow()
    else:
        result = service.send_follow_up_email(
            lead_id=lead.id,
            to_email=lead.primary_contact.email,
            decision_maker_name=lead.primary_contact.name or "",
            company_name=lead.company.name,
        )

    return result
