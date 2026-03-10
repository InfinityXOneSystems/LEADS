"""Scoring factors and criteria."""
from typing import Optional
from pydantic import BaseModel
from datetime import datetime


class ScoringBreakdown(BaseModel):
    business_legitimacy: float = 0.0
    epoxy_relevance: float = 0.0
    market_opportunity: float = 0.0
    recent_activity: float = 0.0
    decision_maker_accessibility: float = 0.0
    growth_trajectory: float = 0.0
    competitor_proximity: float = 0.0
    social_engagement: float = 0.0


class ScoreFactors(BaseModel):
    overall_score: int = 0
    buying_likelihood: float = 0.0
    confidence: float = 0.0
    scoring_breakdown: ScoringBreakdown = ScoringBreakdown()
    scored_at: Optional[datetime] = None
    scoring_model_version: str = "v1.0"

    class Config:
        from_attributes = True
