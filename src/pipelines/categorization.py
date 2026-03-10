"""Lead categorization pipeline (Hot/Warm/Cold)."""
from typing import List
from ..models.lead import Lead
from ..utils.logger import get_logger
from ..config import settings

logger = get_logger(__name__)


class CategorizationPipeline:
    """Categorizes leads into Hot, Warm, or Cold buckets."""

    def categorize(self, lead: Lead) -> Lead:
        """Assign category based on overall score."""
        score = lead.scores.overall_score

        if score >= settings.hot_score_threshold:
            lead.category = "hot"
        elif score >= settings.warm_score_threshold:
            lead.category = "warm"
        else:
            lead.category = "cold"

        lead.tags = self._generate_tags(lead)
        logger.info(f"Lead {lead.id} categorized as {lead.category} (score={score})")
        return lead

    def rank_leads(self, leads: List[Lead]) -> List[Lead]:
        """Rank leads within their category."""
        hot = sorted(
            [l for l in leads if l.category == "hot"],
            key=lambda x: x.scores.overall_score, reverse=True
        )
        warm = sorted(
            [l for l in leads if l.category == "warm"],
            key=lambda x: x.scores.overall_score, reverse=True
        )
        cold = sorted(
            [l for l in leads if l.category == "cold"],
            key=lambda x: x.scores.overall_score, reverse=True
        )

        for i, lead in enumerate(hot, 1):
            lead.category_rank = i
        for i, lead in enumerate(warm, 1):
            lead.category_rank = i
        for i, lead in enumerate(cold, 1):
            lead.category_rank = i

        return hot + warm + cold

    def _generate_tags(self, lead: Lead) -> List[str]:
        """Generate tags based on lead characteristics."""
        tags = []

        social = lead.company.social_presence
        active_channels = sum([
            bool(social.facebook), bool(social.instagram),
            bool(social.linkedin), bool(social.youtube)
        ])
        if active_channels >= 3:
            tags.append("active-social")

        if lead.company.google_reviews_count and lead.company.google_reviews_count > 50:
            tags.append("high-volume")

        if lead.company.website_has_epoxy_mention:
            tags.append("epoxy-potential")

        if lead.scores.scoring_breakdown.epoxy_relevance > 0.7:
            tags.append("high-relevance")

        if lead.company.employee_count and (
            "50-200" in lead.company.employee_count or "100+" in lead.company.employee_count
        ):
            tags.append("growing-business")

        if lead.company.business_status == "active":
            tags.append("verified-active")

        if lead.primary_contact.email_verified and lead.primary_contact.phone_verified:
            tags.append("verified-contact")

        return tags
