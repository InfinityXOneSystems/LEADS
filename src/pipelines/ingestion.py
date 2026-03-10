"""Raw lead intake pipeline."""
from datetime import datetime
from typing import Dict, Any, List
from ..models.lead import Lead
from ..models.company import Company, SocialPresence
from ..models.contact import Contact
from ..utils.logger import get_logger
from ..utils.validators import PhoneValidator, EmailValidator

logger = get_logger(__name__)


class IngestionPipeline:
    """Ingests raw lead data from various scraping sources."""

    VALID_SOURCES = {
        "google_maps", "linkedin", "craigslist", "yelp", "yellowpages",
        "bbb", "angieslist", "homeadvisor", "thumbtack", "houzz",
        "directory", "facebook", "instagram", "twitter", "website",
        "manual", "referral", "trade_show", "cold_call", "other"
    }

    def ingest(self, raw_data: Dict[str, Any]) -> Lead:
        """Process raw lead data into a Lead object."""
        start_time = datetime.utcnow()
        logger.info(f"Ingesting lead from source: {raw_data.get('source', 'unknown')}")

        company = self._extract_company(raw_data)
        primary_contact = self._extract_primary_contact(raw_data)
        secondary_contacts = self._extract_secondary_contacts(raw_data)

        source = raw_data.get("source", "other")
        if source not in self.VALID_SOURCES:
            source = "other"

        lead = Lead(
            source=source,
            scraped_at=raw_data.get("scraped_at") or datetime.utcnow(),
            company=company,
            primary_contact=primary_contact,
            secondary_contacts=secondary_contacts,
        )

        elapsed = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        lead.processing_time_ms = elapsed
        logger.info(f"Lead ingested: {lead.id} in {elapsed}ms")
        return lead

    def _extract_company(self, raw_data: Dict[str, Any]) -> Company:
        """Extract company data from raw input."""
        company_data = raw_data.get("company", raw_data)

        phone_raw = company_data.get("phone") or company_data.get("company_phone")
        phone = PhoneValidator.to_e164(phone_raw) if phone_raw else None

        social_data = company_data.get("social_presence", {})
        if not isinstance(social_data, dict):
            social_data = {}
        social = SocialPresence(
            facebook=social_data.get("facebook"),
            instagram=social_data.get("instagram"),
            linkedin=social_data.get("linkedin"),
            youtube=social_data.get("youtube"),
            twitter=social_data.get("twitter"),
        )

        return Company(
            name=company_data.get("name", company_data.get("company_name", "")),
            website=company_data.get("website"),
            phone=phone,
            address=company_data.get("address"),
            city=company_data.get("city"),
            state=company_data.get("state"),
            zip=company_data.get("zip"),
            country=company_data.get("country", "US"),
            founded_year=company_data.get("founded_year"),
            employee_count=company_data.get("employee_count"),
            revenue_estimate=company_data.get("revenue_estimate"),
            business_status=company_data.get("business_status"),
            industry=company_data.get("industry"),
            specializations=company_data.get("specializations", []),
            google_rating=company_data.get("google_rating"),
            google_reviews_count=company_data.get("google_reviews_count"),
            yelp_rating=company_data.get("yelp_rating"),
            yelp_reviews_count=company_data.get("yelp_reviews_count"),
            social_presence=social,
            website_seo_score=company_data.get("website_seo_score"),
            website_has_epoxy_mention=company_data.get("website_has_epoxy_mention", False),
            website_conversion_signals=company_data.get("website_conversion_signals", []),
        )

    def _extract_primary_contact(self, raw_data: Dict[str, Any]) -> Contact:
        """Extract primary contact from raw data."""
        contact_data = raw_data.get("primary_contact", raw_data.get("contact", {}))
        if not isinstance(contact_data, dict):
            contact_data = {}

        email_raw = contact_data.get("email") or raw_data.get("email")
        email = EmailValidator.normalize(email_raw) if email_raw else None

        phone_raw = contact_data.get("phone") or raw_data.get("contact_phone")
        phone = PhoneValidator.to_e164(phone_raw) if phone_raw else None

        return Contact(
            name=contact_data.get("name") or raw_data.get("contact_name"),
            title=contact_data.get("title") or raw_data.get("contact_title"),
            phone=phone,
            email=email,
            linkedin_url=contact_data.get("linkedin_url"),
        )

    def _extract_secondary_contacts(self, raw_data: Dict[str, Any]) -> List[Contact]:
        """Extract secondary contacts."""
        contacts = []
        for cd in raw_data.get("secondary_contacts", []):
            if not isinstance(cd, dict):
                continue
            email_raw = cd.get("email")
            email = EmailValidator.normalize(email_raw) if email_raw else None
            phone_raw = cd.get("phone")
            phone = PhoneValidator.to_e164(phone_raw) if phone_raw else None
            contacts.append(Contact(
                name=cd.get("name"),
                title=cd.get("title"),
                phone=phone,
                email=email,
                linkedin_url=cd.get("linkedin_url"),
            ))
        return contacts
