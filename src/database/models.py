"""SQLAlchemy database models."""
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Float, Integer, Boolean,
    DateTime, ForeignKey, Text, Index, UniqueConstraint
)
from sqlalchemy.orm import DeclarativeBase, relationship


def generate_uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class LeadDB(Base):
    __tablename__ = "leads"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    source = Column(String(50))
    scraped_at = Column(DateTime)

    company_name = Column(String(255), nullable=False)
    company_website = Column(String(500))
    company_address = Column(String(500))
    company_city = Column(String(100))
    company_state = Column(String(50))
    company_zip = Column(String(20))
    company_phone = Column(String(20))
    company_rating = Column(Float)
    company_reviews_count = Column(Integer)
    company_status = Column(String(50))
    company_industry = Column(String(255))
    company_employee_count = Column(String(50))
    company_revenue_estimate = Column(String(100))
    company_founded_year = Column(Integer)
    company_specializations = Column(Text)
    website_has_epoxy_mention = Column(Boolean, default=False)

    primary_contact_name = Column(String(255))
    primary_contact_title = Column(String(255))
    primary_contact_email = Column(String(255))
    primary_contact_phone = Column(String(20))
    primary_contact_linkedin = Column(String(500))
    primary_contact_email_verified = Column(Boolean, default=False)
    primary_contact_phone_verified = Column(Boolean, default=False)

    overall_score = Column(Integer, default=0)
    buying_likelihood = Column(Float, default=0.0)
    confidence_score = Column(Float, default=0.0)
    category = Column(String(20))
    category_rank = Column(Integer)

    outreach_email_sent = Column(Boolean, default=False)
    outreach_email_sent_at = Column(DateTime)
    outreach_email_opened = Column(Boolean, default=False)
    outreach_email_opened_at = Column(DateTime)
    follow_up_scheduled = Column(Boolean, default=False)
    follow_up_date = Column(DateTime)

    data_quality_score = Column(Float, default=0.0)
    validation_status = Column(String(50), default="pending")
    missing_fields = Column(Text)
    flagged_issues = Column(Text)

    tags = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    version = Column(Integer, default=1)
    processing_time_ms = Column(Integer)

    scores = relationship("LeadScoreDB", back_populates="lead", uselist=False,
                          cascade="all, delete-orphan")
    contacts = relationship("LeadContactDB", back_populates="lead",
                            cascade="all, delete-orphan")
    outreach_logs = relationship("OutreachLogDB", back_populates="lead",
                                  cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("company_phone", "primary_contact_email",
                         name="uq_leads_phone_email"),
        Index("idx_leads_overall_score", "overall_score"),
        Index("idx_leads_category", "category"),
        Index("idx_leads_created_at", "created_at"),
        Index("idx_leads_phone", "company_phone"),
        Index("idx_leads_email", "primary_contact_email"),
    )


class LeadScoreDB(Base):
    __tablename__ = "lead_scores"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    lead_id = Column(String(36), ForeignKey("leads.id"), nullable=False)
    legitimacy_score = Column(Float, default=0.0)
    relevance_score = Column(Float, default=0.0)
    opportunity_score = Column(Float, default=0.0)
    activity_score = Column(Float, default=0.0)
    accessibility_score = Column(Float, default=0.0)
    engagement_score = Column(Float, default=0.0)
    growth_trajectory_score = Column(Float, default=0.0)
    scoring_model_version = Column(String(20))
    created_at = Column(DateTime, default=datetime.utcnow)

    lead = relationship("LeadDB", back_populates="scores")


class LeadContactDB(Base):
    __tablename__ = "lead_contacts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    lead_id = Column(String(36), ForeignKey("leads.id"), nullable=False)
    contact_type = Column(String(50), default="secondary")
    name = Column(String(255))
    title = Column(String(255))
    email = Column(String(255))
    phone = Column(String(20))
    linkedin_url = Column(String(500))
    email_verified = Column(Boolean, default=False)
    phone_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    lead = relationship("LeadDB", back_populates="contacts")


class OutreachLogDB(Base):
    __tablename__ = "outreach_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    lead_id = Column(String(36), ForeignKey("leads.id"), nullable=False)
    email_type = Column(String(50))
    sent_at = Column(DateTime)
    opened_at = Column(DateTime)
    clicked_at = Column(DateTime)
    success = Column(Boolean, default=True)
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    lead = relationship("LeadDB", back_populates="outreach_logs")
