"""Company data model."""
from typing import Optional, List
from pydantic import BaseModel


class SocialPresence(BaseModel):
    facebook: Optional[str] = None
    instagram: Optional[str] = None
    linkedin: Optional[str] = None
    youtube: Optional[str] = None
    twitter: Optional[str] = None


class Company(BaseModel):
    name: str
    website: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    country: str = "US"

    # Enriched data
    founded_year: Optional[int] = None
    employee_count: Optional[str] = None
    revenue_estimate: Optional[str] = None
    business_status: Optional[str] = None
    industry: Optional[str] = None
    specializations: List[str] = []
    google_rating: Optional[float] = None
    google_reviews_count: Optional[int] = None
    yelp_rating: Optional[float] = None
    yelp_reviews_count: Optional[int] = None
    social_presence: SocialPresence = SocialPresence()
    website_seo_score: Optional[int] = None
    website_has_epoxy_mention: bool = False
    website_conversion_signals: List[str] = []

    class Config:
        from_attributes = True
