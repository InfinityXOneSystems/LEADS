"""Lead scoring pipeline."""
from datetime import datetime
from typing import Dict
from ..models.lead import Lead
from ..models.score_factors import ScoringBreakdown, ScoreFactors
from ..utils.logger import get_logger

logger = get_logger(__name__)

SCORING_MODEL_VERSION = "v1.0"

WEIGHTS = {
    "legitimacy": 0.20,
    "relevance": 0.25,
    "opportunity": 0.15,
    "activity": 0.15,
    "accessibility": 0.15,
    "engagement": 0.10,
}

EPOXY_KEYWORDS = {
    "epoxy", "concrete", "flooring", "polished", "coating", "grind",
    "seal", "metallic", "flake", "quartz", "polyurea", "polyaspartic",
    "surface prep", "diamond", "decorative", "industrial flooring"
}


class ScoringPipeline:
    """Multi-factor lead scoring system."""

    def score(self, lead: Lead) -> Lead:
        """Score a lead on 0-100 scale."""
        logger.info(f"Scoring lead: {lead.id}")

        factors = {
            "legitimacy": self._score_legitimacy(lead),
            "relevance": self._score_epoxy_relevance(lead),
            "opportunity": self._score_opportunity(lead),
            "activity": self._score_activity(lead),
            "accessibility": self._score_accessibility(lead),
            "engagement": self._score_engagement(lead),
        }

        overall = sum(factors[k] * WEIGHTS[k] for k in WEIGHTS)
        overall_score = min(100, max(0, int(overall * 100)))
        buying_likelihood = round(overall, 4)
        confidence = self._calculate_confidence(lead)

        breakdown = ScoringBreakdown(
            business_legitimacy=round(factors["legitimacy"], 4),
            epoxy_relevance=round(factors["relevance"], 4),
            market_opportunity=round(factors["opportunity"], 4),
            recent_activity=round(factors["activity"], 4),
            decision_maker_accessibility=round(factors["accessibility"], 4),
            social_engagement=round(factors["engagement"], 4),
            growth_trajectory=round(factors["opportunity"], 4),
            competitor_proximity=0.5,
        )

        lead.scores = ScoreFactors(
            overall_score=overall_score,
            buying_likelihood=buying_likelihood,
            confidence=confidence,
            scoring_breakdown=breakdown,
            scored_at=datetime.utcnow(),
            scoring_model_version=SCORING_MODEL_VERSION,
        )

        logger.info(f"Lead {lead.id} scored: {overall_score}/100")
        return lead

    def _score_legitimacy(self, lead: Lead) -> float:
        """Score business legitimacy (0-1)."""
        score = 0.5

        status = (lead.company.business_status or "").lower()
        if status == "active":
            score += 0.3
        elif status in ("inactive", "closed", "dissolved"):
            score -= 0.4
        elif status == "unknown":
            score -= 0.1

        if lead.company.google_rating:
            score += 0.1
        if lead.company.google_reviews_count and lead.company.google_reviews_count > 10:
            score += 0.05
        if lead.company.website:
            score += 0.05

        return min(1.0, max(0.0, score))

    def _score_epoxy_relevance(self, lead: Lead) -> float:
        """Score epoxy/concrete relevance (0-1)."""
        score = 0.0
        text_to_check = []

        if lead.company.specializations:
            text_to_check.extend(lead.company.specializations)
        if lead.company.industry:
            text_to_check.append(lead.company.industry)

        combined = " ".join(text_to_check).lower()
        keyword_matches = sum(1 for kw in EPOXY_KEYWORDS if kw in combined)

        if keyword_matches >= 3:
            score = 0.9
        elif keyword_matches == 2:
            score = 0.7
        elif keyword_matches == 1:
            score = 0.5
        else:
            score = 0.2

        if lead.company.website_has_epoxy_mention:
            score = min(1.0, score + 0.1)

        return min(1.0, max(0.0, score))

    def _score_opportunity(self, lead: Lead) -> float:
        """Score market opportunity (0-1)."""
        score = 0.5

        emp = lead.company.employee_count or ""
        if "50-200" in emp or "100+" in emp:
            score += 0.2
        elif "10-50" in emp or "50+" in emp:
            score += 0.1
        elif "1-10" in emp or "small" in emp.lower():
            score -= 0.05

        rev = lead.company.revenue_estimate or ""
        if "$10M" in rev or "$20M" in rev or "$50M" in rev:
            score += 0.2
        elif "$5M" in rev or "$2M" in rev:
            score += 0.1
        elif "$1M" in rev:
            score += 0.05

        return min(1.0, max(0.0, score))

    def _score_activity(self, lead: Lead) -> float:
        """Score recent activity (0-1)."""
        score = 0.5

        if lead.company.google_reviews_count:
            if lead.company.google_reviews_count > 50:
                score += 0.2
            elif lead.company.google_reviews_count > 20:
                score += 0.1

        social = lead.company.social_presence
        active_channels = sum([
            bool(social.facebook),
            bool(social.instagram),
            bool(social.linkedin),
            bool(social.youtube),
        ])
        score += active_channels * 0.05

        return min(1.0, max(0.0, score))

    def _score_accessibility(self, lead: Lead) -> float:
        """Score decision maker accessibility (0-1)."""
        score = 0.3

        if lead.primary_contact.phone:
            score += 0.25
        if lead.primary_contact.email:
            score += 0.25
        if lead.primary_contact.name:
            score += 0.1
        if lead.primary_contact.linkedin_url:
            score += 0.05
        if lead.primary_contact.email_verified:
            score += 0.05

        return min(1.0, max(0.0, score))

    def _score_engagement(self, lead: Lead) -> float:
        """Score social engagement (0-1)."""
        score = 0.2
        social = lead.company.social_presence
        channels = [
            social.facebook, social.instagram,
            social.linkedin, social.youtube
        ]
        active = sum(1 for c in channels if c)
        score += active * 0.15
        conversion_signals = lead.company.website_conversion_signals or []
        score += len(conversion_signals) * 0.05
        return min(1.0, max(0.0, score))

    def _calculate_confidence(self, lead: Lead) -> float:
        """Calculate confidence in the score (0-1)."""
        completeness = lead.data_quality.completeness_score
        base_confidence = 0.5 + (completeness * 0.4)
        if lead.primary_contact.email_verified:
            base_confidence += 0.05
        if lead.primary_contact.phone_verified:
            base_confidence += 0.05
        return min(1.0, round(base_confidence, 4))
