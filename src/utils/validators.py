"""Validation helper utilities."""
import re
from typing import Optional

try:
    import phonenumbers
    PHONENUMBERS_AVAILABLE = True
except ImportError:
    PHONENUMBERS_AVAILABLE = False


class PhoneValidator:
    """Phone number validation and formatting."""

    E164_PATTERN = re.compile(r"^\+?1?\d{10,15}$")
    US_PATTERN = re.compile(r"^\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}$")

    @classmethod
    def is_valid(cls, phone: str) -> bool:
        """Check if a phone number has a valid format."""
        if not phone:
            return False
        cleaned = re.sub(r"[\s\-\(\)\.ext]+", "", phone)
        if PHONENUMBERS_AVAILABLE:
            try:
                parsed = phonenumbers.parse(phone, "US")
                if phonenumbers.is_valid_number(parsed):
                    return True
            except Exception:
                pass
        return bool(cls.E164_PATTERN.match(cleaned))

    @classmethod
    def to_e164(cls, phone: str) -> Optional[str]:
        """Convert phone to E.164 format."""
        if not phone:
            return None
        if PHONENUMBERS_AVAILABLE:
            try:
                parsed = phonenumbers.parse(phone, "US")
                if phonenumbers.is_valid_number(parsed):
                    return phonenumbers.format_number(
                        parsed, phonenumbers.PhoneNumberFormat.E164
                    )
            except Exception:
                pass
        cleaned = re.sub(r"[\s\-\(\)\.ext]+", "", phone)
        if not cleaned.startswith("+"):
            if len(cleaned) == 10:
                cleaned = "+1" + cleaned
            elif len(cleaned) == 11 and cleaned.startswith("1"):
                cleaned = "+" + cleaned
        return cleaned if cls.E164_PATTERN.match(cleaned) else None

    @classmethod
    def to_display(cls, phone: str) -> Optional[str]:
        """Format phone for display: +1 (555) 123-4567."""
        e164 = cls.to_e164(phone)
        if not e164:
            return None
        digits = re.sub(r"\D", "", e164)
        if len(digits) == 11 and digits.startswith("1"):
            digits = digits[1:]
        if len(digits) == 10:
            return f"+1 ({digits[:3]}) {digits[3:6]}-{digits[6:]}"
        return phone

    @classmethod
    def to_tel_link(cls, phone: str) -> Optional[str]:
        """Convert to tel: link for mobile."""
        e164 = cls.to_e164(phone)
        if not e164:
            return None
        return f"tel:{e164}"


class EmailValidator:
    """Email address validation."""

    EMAIL_PATTERN = re.compile(
        r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
    )

    @classmethod
    def is_valid(cls, email: str) -> bool:
        """Check if an email address is valid format."""
        if not email:
            return False
        return bool(cls.EMAIL_PATTERN.match(email.strip().lower()))

    @classmethod
    def normalize(cls, email: str) -> Optional[str]:
        """Normalize email to lowercase."""
        if not cls.is_valid(email):
            return None
        return email.strip().lower()

    @classmethod
    def to_mailto_link(cls, email: str) -> Optional[str]:
        """Convert to mailto: link."""
        normalized = cls.normalize(email)
        if not normalized:
            return None
        return f"mailto:{normalized}"


class AddressValidator:
    """Address validation."""

    @classmethod
    def is_valid(cls, address: str) -> bool:
        """Basic address validation."""
        if not address or len(address.strip()) < 5:
            return False
        parts = address.strip().split()
        return len(parts) >= 2

    @classmethod
    def normalize(cls, address: str) -> Optional[str]:
        """Normalize address string."""
        if not cls.is_valid(address):
            return None
        return " ".join(address.strip().split())
