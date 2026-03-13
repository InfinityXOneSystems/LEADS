"""XPS Intelligence sync service.

Exports normalized lead data as structured JSON for GitHub Pages and
dispatches update events to the XPS Intelligence Frontend repo.
"""
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from ..utils.logger import get_logger

logger = get_logger(__name__)

# Schema version for the exported payload – bump on breaking changes.
EXPORT_SCHEMA_VERSION = "1.0"


class XPSSyncService:
    """Push normalized lead data to GitHub Pages and the XPS Frontend."""

    def __init__(
        self,
        github_token: str = "",
        xps_system_repo: str = "InfinityXOneSystems/LEADS",
        xps_frontend_repo: str = "InfinityXOneSystems/frontend-system",
        pages_branch: str = "gh-pages",
    ):
        self.github_token = github_token
        self.xps_system_repo = xps_system_repo
        self.xps_frontend_repo = xps_frontend_repo
        self.pages_branch = pages_branch
        self._last_sync_at: Optional[datetime] = None
        self._last_sync_status: str = "never"
        self._last_sync_counts: Dict[str, int] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_export_payload(self, leads: List[Any]) -> Dict[str, Any]:
        """Convert processed Lead objects into a serializable export payload.

        The payload is the canonical format shared between this repo and all
        XPS consumer systems.  Any consumer receiving this JSON can render
        leads without running the full Python pipeline.
        """
        now = datetime.now(timezone.utc).isoformat()
        serialized = [self._serialize_lead(lead) for lead in leads]

        hot = [l for l in serialized if l.get("category") == "hot"]
        warm = [l for l in serialized if l.get("category") == "warm"]
        cold = [l for l in serialized if l.get("category") == "cold"]

        return {
            "schema_version": EXPORT_SCHEMA_VERSION,
            "exported_at": now,
            "source_repo": self.xps_system_repo,
            "totals": {
                "all": len(serialized),
                "hot": len(hot),
                "warm": len(warm),
                "cold": len(cold),
            },
            "leads": serialized,
            "hot": hot,
            "warm": warm,
            "cold": cold,
        }

    def dispatch_frontend_update(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send a ``repository_dispatch`` event to the XPS Intelligence Frontend.

        The frontend CI/CD workflow listens for the ``leads-updated`` event type
        and rebuilds/redeploys with the latest data automatically.
        """
        if not self.github_token:
            logger.warning("XPS_GITHUB_TOKEN not set – skipping frontend dispatch")
            return {"success": False, "reason": "no_token"}

        url = f"https://api.github.com/repos/{self.xps_frontend_repo}/dispatches"
        headers = {
            "Authorization": f"Bearer {self.github_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        body = {
            "event_type": "leads-updated",
            "client_payload": {
                "schema_version": payload.get("schema_version"),
                "exported_at": payload.get("exported_at"),
                "source_repo": self.xps_system_repo,
                "totals": payload.get("totals", {}),
            },
        }

        try:
            with httpx.Client(timeout=15.0) as client:
                response = client.post(url, json=body, headers=headers)

            if response.status_code == 204:
                logger.info(
                    f"Dispatched 'leads-updated' to {self.xps_frontend_repo}"
                )
                return {"success": True, "status_code": 204}

            logger.warning(
                f"Frontend dispatch returned HTTP {response.status_code}: "
                f"{response.text[:200]}"
            )
            return {
                "success": False,
                "status_code": response.status_code,
                "reason": response.text[:200],
            }
        except Exception as exc:
            logger.error(f"Frontend dispatch failed: {exc}")
            return {"success": False, "reason": str(exc)}

    def sync(self, leads: List[Any]) -> Dict[str, Any]:
        """Run a full sync: build payload, dispatch to frontend, record status.

        The GitHub Pages deployment itself is handled by the
        `.github/workflows/sync-to-pages.yml` CI/CD pipeline which commits the
        exported JSON to the ``gh-pages`` branch.  This method produces the
        payload and notifies downstream systems.
        """
        payload = self.build_export_payload(leads)
        dispatch_result = self.dispatch_frontend_update(payload)

        self._last_sync_at = datetime.now(timezone.utc)
        self._last_sync_status = "ok" if dispatch_result.get("success") else "partial"
        self._last_sync_counts = payload.get("totals", {})

        result = {
            "synced_at": self._last_sync_at.isoformat(),
            "status": self._last_sync_status,
            "totals": payload["totals"],
            "dispatch": dispatch_result,
        }
        logger.info(f"XPS sync complete: {result}")
        return result

    def get_status(self) -> Dict[str, Any]:
        """Return the status of the most recent sync."""
        return {
            "last_sync_at": (
                self._last_sync_at.isoformat() if self._last_sync_at else None
            ),
            "last_sync_status": self._last_sync_status,
            "last_sync_counts": self._last_sync_counts,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _serialize_lead(lead: Any) -> Dict[str, Any]:
        """Convert a Lead object (or dict) to a plain serializable dict."""
        if hasattr(lead, "model_dump"):
            raw = lead.model_dump()
        elif isinstance(lead, dict):
            raw = lead
        else:
            raw = {}

        company = raw.get("company") or {}
        contact = raw.get("primary_contact") or {}
        scores = raw.get("scores") or {}
        frontend = raw.get("frontend") or {}

        created_at = raw.get("created_at")
        if isinstance(created_at, datetime):
            created_at = created_at.isoformat()

        return {
            "id": raw.get("id", ""),
            "source": raw.get("source"),
            "category": raw.get("category"),
            "category_rank": raw.get("category_rank"),
            "overall_score": scores.get("overall_score", 0),
            "buying_likelihood": scores.get("buying_likelihood", 0.0),
            "confidence": scores.get("confidence", 0.0),
            "tags": raw.get("tags", []),
            "company": {
                "name": company.get("name", ""),
                "website": company.get("website"),
                "phone": company.get("phone"),
                "address": company.get("address"),
                "city": company.get("city"),
                "state": company.get("state"),
                "zip": company.get("zip"),
                "country": company.get("country", "US"),
                "industry": company.get("industry"),
                "specializations": company.get("specializations", []),
                "business_status": company.get("business_status"),
                "google_rating": company.get("google_rating"),
                "google_reviews_count": company.get("google_reviews_count"),
                "employee_count": company.get("employee_count"),
                "revenue_estimate": company.get("revenue_estimate"),
            },
            "contact": {
                "name": contact.get("name"),
                "title": contact.get("title"),
                "email": contact.get("email"),
                "phone": contact.get("phone"),
            },
            "display": {
                "display_name": frontend.get("display_name", ""),
                "display_phone": frontend.get("display_phone"),
                "display_phone_link": frontend.get("display_phone_link"),
                "display_email": frontend.get("display_email"),
                "display_email_link": frontend.get("display_email_link"),
                "avatar_url": frontend.get("avatar_url"),
                "description": frontend.get("description"),
                "key_facts": frontend.get("key_facts", []),
            },
            "created_at": created_at,
        }

    @staticmethod
    def export_to_json(payload: Dict[str, Any], indent: int = 2) -> str:
        """Serialize export payload to a JSON string."""
        return json.dumps(payload, indent=indent, default=str)
