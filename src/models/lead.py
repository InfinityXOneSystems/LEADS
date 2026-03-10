"""Lead data model."""
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from .contact import Contact
from .company import Company
from .score_factors import ScoreFactors


class OutreachStatus(BaseModel):
    initial_email_sent: bool = False
    initial_email_sent_at: Optional[datetime] = None
    initial_email_opened: bool = False
    initial_email_opened_at: Optional[datetime] = None
    initial_email_clicked: bool = False
    clicked_link: Optional[str] = None
    follow_up_scheduled: bool = False
    follow_up_date: Optional[datetime] = None
    contacted_by_sales_rep: bool = False
    sales_rep_name: Optional[str] = None
    sales_rep_notes: Optional[str] = None


class DataQuality(BaseModel):
    completeness_score: float = 0.0
    validation_status: str = "pending"
    missing_fields: List[str] = []
    flagged_issues: List[str] = []


class FrontendFormat(BaseModel):
    display_name: str = ""
    display_phone: Optional[str] = None
    display_phone_link: Optional[str] = None
    display_email: Optional[str] = None
    display_email_link: Optional[str] = None
    avatar_url: Optional[str] = None
    hero_image: Optional[str] = None
    description: Optional[str] = None
    key_facts: List[str] = []


class Lead(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source: Optional[str] = None
    scraped_at: Optional[datetime] = None

    company: Company
    primary_contact: Contact = Contact()
    secondary_contacts: List[Contact] = []

    scores: ScoreFactors = ScoreFactors()
    category: Optional[str] = None
    category_rank: Optional[int] = None
    tags: List[str] = []

    outreach: OutreachStatus = OutreachStatus()
    data_quality: DataQuality = DataQuality()
    frontend: FrontendFormat = FrontendFormat()

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    version: int = 1
    processing_time_ms: Optional[int] = None

    class Config:
        from_attributes = True
