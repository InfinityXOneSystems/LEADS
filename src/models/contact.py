"""Contact data model."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class Contact(BaseModel):
    name: Optional[str] = None
    title: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    linkedin_url: Optional[str] = None
    email_verified: bool = False
    phone_verified: bool = False
    previously_contacted: bool = False
    last_contact_date: Optional[datetime] = None

    class Config:
        from_attributes = True
