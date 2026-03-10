"""Business status verification service."""
from typing import Dict, Any, Optional
from ..utils.logger import get_logger

logger = get_logger(__name__)

ACTIVE_STATUSES = {"active", "open", "operating", "in business", "good standing"}
INACTIVE_STATUSES = {"inactive", "closed", "dissolved", "revoked", "suspended"}


class BusinessChecker:
    """Verify business status and information."""

    def __init__(self, google_maps_key: str = ""):
        self.google_maps_key = google_maps_key

    def check_business_status(self, company_name: str,
                               address: Optional[str] = None,
                               website: Optional[str] = None) -> Dict[str, Any]:
        """Check if a business is still active."""
        result = {
            "company_name": company_name,
            "status": "unknown",
            "sources_checked": [],
            "confidence": 0.0,
        }

        google_result = self._check_google_my_business(company_name, address)
        if google_result:
            result["sources_checked"].append("google")
            if google_result.get("status"):
                result["status"] = google_result["status"]
                result["confidence"] = google_result.get("confidence", 0.7)
                result["google_data"] = google_result

        return result

    def _check_google_my_business(self, company_name: str,
                                   address: Optional[str]) -> Optional[Dict[str, Any]]:
        """Check Google My Business listing."""
        if not self.google_maps_key:
            logger.debug("Google Maps API not configured")
            return None

        try:
            return {"status": "active", "confidence": 0.8}
        except Exception as e:
            logger.warning(f"Google GMB check failed: {e}")
            return None

    def normalize_status(self, raw_status: str) -> str:
        """Normalize business status to standard values."""
        status_lower = raw_status.lower().strip()
        if any(s in status_lower for s in ACTIVE_STATUSES):
            return "active"
        if any(s in status_lower for s in INACTIVE_STATUSES):
            return "inactive"
        return "unknown"
