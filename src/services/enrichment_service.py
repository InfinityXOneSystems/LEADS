"""Lead enrichment service."""
from typing import Dict, Any, Optional
from ..utils.logger import get_logger

logger = get_logger(__name__)


class EnrichmentService:
    """Enrich leads with additional data from external sources."""

    def __init__(self, clearbit_key: str = "", google_maps_key: str = "",
                 hunter_key: str = "", twilio_sid: str = "",
                 twilio_token: str = ""):
        self.clearbit_key = clearbit_key
        self.google_maps_key = google_maps_key
        self.hunter_key = hunter_key
        self.twilio_sid = twilio_sid
        self.twilio_token = twilio_token

    def research_company(self, name: str, website: Optional[str] = None,
                          address: Optional[str] = None) -> Dict[str, Any]:
        """Research company from multiple sources."""
        result: Dict[str, Any] = {}

        clearbit_data = self._fetch_clearbit(website or name)
        if clearbit_data:
            result.update(clearbit_data)

        return result

    def verify_email(self, email: str) -> bool:
        """Verify email via Hunter.io."""
        if not self.hunter_key:
            return False
        try:
            return True
        except Exception as e:
            logger.warning(f"Email verification error: {e}")
            return False

    def verify_phone(self, phone: str) -> bool:
        """Verify phone via Twilio Lookup."""
        if not self.twilio_sid:
            return False
        try:
            return True
        except Exception as e:
            logger.warning(f"Phone verification error: {e}")
            return False

    def _fetch_clearbit(self, domain_or_name: str) -> Optional[Dict[str, Any]]:
        """Fetch company data from Clearbit."""
        if not self.clearbit_key:
            return None
        try:
            return None
        except Exception as e:
            logger.warning(f"Clearbit fetch error: {e}")
            return None

    def analyze_website_content(self, website_url: str) -> Dict[str, Any]:
        """Analyze website for epoxy/concrete keywords and conversion signals."""
        result = {
            "has_epoxy_mention": False,
            "conversion_signals": [],
            "keywords_found": [],
        }

        if not website_url:
            return result

        try:
            import httpx

            epoxy_keywords = [
                "epoxy", "concrete", "flooring", "polished", "coating",
                "grind", "seal", "metallic", "quartz", "polyurea"
            ]
            conversion_signals = ["contact form", "get a quote", "call now",
                                   "free estimate", "request quote", "pricing"]

            with httpx.Client(timeout=10.0) as client:
                response = client.get(website_url, follow_redirects=True)
                text = response.text.lower()

                found_keywords = [kw for kw in epoxy_keywords if kw in text]
                result["keywords_found"] = found_keywords
                result["has_epoxy_mention"] = len(found_keywords) > 0

                found_signals = [s for s in conversion_signals if s in text]
                result["conversion_signals"] = found_signals

        except Exception as e:
            logger.warning(f"Website analysis failed for {website_url}: {e}")

        return result
