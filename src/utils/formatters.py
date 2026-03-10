"""Lead formatting utilities for frontend display."""
from typing import Optional, List
from .validators import PhoneValidator, EmailValidator
from .logger import get_logger

logger = get_logger(__name__)


class LeadFormatter:
    """Format lead data for frontend consumption."""

    @classmethod
    def format_phone(cls, phone: Optional[str]) -> Optional[str]:
        if not phone:
            return None
        return PhoneValidator.to_display(phone)

    @classmethod
    def format_phone_link(cls, phone: Optional[str]) -> Optional[str]:
        if not phone:
            return None
        return PhoneValidator.to_tel_link(phone)

    @classmethod
    def format_email_link(cls, email: Optional[str]) -> Optional[str]:
        if not email:
            return None
        return EmailValidator.to_mailto_link(email)

    @classmethod
    def format_avatar_url(cls, website: Optional[str]) -> Optional[str]:
        """Generate avatar URL from Clearbit logo API."""
        if not website:
            return None
        domain = website.replace("https://", "").replace("http://", "").rstrip("/")
        domain = domain.split("/")[0]
        return f"https://logo.clearbit.com/{domain}"

    @classmethod
    def format_description(cls, company_data: dict) -> str:
        """Generate description string for display."""
        parts = []
        if company_data.get("founded_year"):
            parts.append(f"Est. {company_data['founded_year']}")
        if company_data.get("employee_count"):
            parts.append(f"{company_data['employee_count']} employees")
        if company_data.get("revenue_estimate"):
            parts.append(company_data["revenue_estimate"])
        if company_data.get("google_rating") and company_data.get("google_reviews_count"):
            parts.append(
                f"{company_data['google_rating']}★ ({company_data['google_reviews_count']} reviews)"
            )
        return " | ".join(parts) if parts else ""

    @classmethod
    def build_key_facts(cls, lead_data: dict) -> List[str]:
        """Build key facts list for sales team."""
        facts = []
        company = lead_data.get("company", {})
        contact = lead_data.get("primary_contact", {})

        specializations = company.get("specializations", [])
        if specializations:
            facts.append(f"Specializes in {', '.join(specializations[:3])}")

        social = company.get("social_presence", {})
        if isinstance(social, dict):
            active_social = [k for k, v in social.items() if v]
        else:
            active_social = []
        if active_social:
            facts.append(f"Active on {', '.join(active_social)}")

        if company.get("google_rating") and company.get("google_rating", 0) >= 4.5:
            facts.append(f"Highly rated: {company['google_rating']}★ on Google")

        if company.get("website_has_epoxy_mention"):
            facts.append("Website mentions epoxy/concrete services")

        if contact.get("name") and contact.get("title"):
            facts.append(f"Decision maker: {contact['name']} ({contact['title']})")

        if company.get("business_status") == "active":
            facts.append("Verified active business")

        return facts

    @classmethod
    def format_lead_for_frontend(cls, lead: dict) -> dict:
        """Format complete lead object for frontend."""
        company = lead.get("company", {})
        contact = lead.get("primary_contact", {})

        phone = contact.get("phone") or company.get("phone")
        email = contact.get("email")
        website = company.get("website")

        return {
            "display_name": company.get("name", ""),
            "display_phone": cls.format_phone(phone),
            "display_phone_link": cls.format_phone_link(phone),
            "display_email": email,
            "display_email_link": cls.format_email_link(email),
            "avatar_url": cls.format_avatar_url(website),
            "hero_image": None,
            "description": cls.format_description(company),
            "key_facts": cls.build_key_facts(lead),
        }
