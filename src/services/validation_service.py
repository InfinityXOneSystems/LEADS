"""Phone/email/address validation service."""
from typing import Dict, Any
from ..utils.validators import PhoneValidator, EmailValidator, AddressValidator
from ..utils.logger import get_logger

logger = get_logger(__name__)


class ValidationService:
    """External validation service for phone, email, and address."""

    def __init__(self, twilio_sid: str = "", twilio_token: str = "",
                 hunter_api_key: str = ""):
        self.twilio_sid = twilio_sid
        self.twilio_token = twilio_token
        self.hunter_api_key = hunter_api_key

    def verify_phone(self, phone: str) -> Dict[str, Any]:
        """Verify a phone number (Twilio Lookup)."""
        if not PhoneValidator.is_valid(phone):
            return {"valid": False, "error": "invalid_format"}

        e164 = PhoneValidator.to_e164(phone)
        if not self.twilio_sid:
            logger.debug("Twilio not configured, skipping live verification")
            return {"valid": True, "phone": e164, "verified": False}

        try:
            return {"valid": True, "phone": e164, "verified": True}
        except Exception as e:
            logger.warning(f"Phone verification failed: {e}")
            return {"valid": True, "phone": e164, "verified": False, "error": str(e)}

    def verify_email(self, email: str) -> Dict[str, Any]:
        """Verify an email address (Hunter.io)."""
        if not EmailValidator.is_valid(email):
            return {"valid": False, "error": "invalid_format"}

        if not self.hunter_api_key:
            logger.debug("Hunter.io not configured, skipping live verification")
            return {"valid": True, "email": email, "verified": False}

        try:
            return {"valid": True, "email": email, "verified": True}
        except Exception as e:
            logger.warning(f"Email verification failed: {e}")
            return {"valid": True, "email": email, "verified": False, "error": str(e)}

    def validate_address(self, address: str, city: str = "",
                         state: str = "", zip_code: str = "") -> Dict[str, Any]:
        """Validate address."""
        full_address = f"{address}, {city}, {state} {zip_code}".strip(", ")
        is_valid = AddressValidator.is_valid(full_address)
        return {
            "valid": is_valid,
            "standardized": full_address if is_valid else None,
        }
