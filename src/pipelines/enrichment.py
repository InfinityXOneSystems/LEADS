"""Data enrichment pipeline."""
from datetime import datetime
from typing import Dict, Any, Optional
from ..models.lead import Lead
from ..utils.logger import get_logger

logger = get_logger(__name__)


class EnrichmentPipeline:
    """Enriches lead data with additional research."""

    def __init__(self, enrichment_service=None):
        self.enrichment_service = enrichment_service

    def enrich(self, lead: Lead) -> Lead:
        """Run enrichment on a lead."""
        logger.info(f"Enriching lead: {lead.id}")
        start = datetime.utcnow()

        lead = self._enrich_company(lead)
        lead = self._enrich_contact(lead)
        lead = self._check_epoxy_relevance(lead)

        elapsed = int((datetime.utcnow() - start).total_seconds() * 1000)
        lead.processing_time_ms = (lead.processing_time_ms or 0) + elapsed
        lead.updated_at = datetime.utcnow()
        logger.info(f"Lead {lead.id} enrichment complete in {elapsed}ms")
        return lead

    def _enrich_company(self, lead: Lead) -> Lead:
        """Enrich company data."""
        if self.enrichment_service and lead.company.website:
            try:
                data = self.enrichment_service.research_company(
                    name=lead.company.name,
                    website=lead.company.website,
                    address=lead.company.address,
                )
                if data:
                    company = lead.company
                    if not company.founded_year and data.get("founded_year"):
                        company.founded_year = data["founded_year"]
                    if not company.employee_count and data.get("employee_count"):
                        company.employee_count = data["employee_count"]
                    if not company.revenue_estimate and data.get("revenue_estimate"):
                        company.revenue_estimate = data["revenue_estimate"]
                    if not company.business_status and data.get("business_status"):
                        company.business_status = data["business_status"]
                    if not company.google_rating and data.get("google_rating"):
                        company.google_rating = data["google_rating"]
                    if not company.google_reviews_count and data.get("google_reviews_count"):
                        company.google_reviews_count = data["google_reviews_count"]
            except Exception as e:
                logger.warning(f"Company enrichment failed for {lead.id}: {e}")

        if not lead.company.business_status:
            lead.company.business_status = "unknown"
        return lead

    def _enrich_contact(self, lead: Lead) -> Lead:
        """Enrich primary contact data."""
        if self.enrichment_service and lead.primary_contact.email:
            try:
                verified = self.enrichment_service.verify_email(
                    lead.primary_contact.email
                )
                lead.primary_contact.email_verified = verified
            except Exception as e:
                logger.warning(f"Email verification failed for {lead.id}: {e}")

        if self.enrichment_service and lead.primary_contact.phone:
            try:
                verified = self.enrichment_service.verify_phone(
                    lead.primary_contact.phone
                )
                lead.primary_contact.phone_verified = verified
            except Exception as e:
                logger.warning(f"Phone verification failed for {lead.id}: {e}")

        return lead

    def _check_epoxy_relevance(self, lead: Lead) -> Lead:
        """Check website/description for epoxy/concrete keywords."""
        epoxy_keywords = {
            "epoxy", "concrete", "flooring", "polished", "coating",
            "grind", "seal", "metallic", "flake", "quartz", "polyurea",
            "polyaspartic", "surface prep", "diamond"
        }

        specialization_text = " ".join(lead.company.specializations).lower()
        industry_text = (lead.company.industry or "").lower()
        combined_text = f"{specialization_text} {industry_text}"

        if any(kw in combined_text for kw in epoxy_keywords):
            lead.company.website_has_epoxy_mention = True

        return lead
