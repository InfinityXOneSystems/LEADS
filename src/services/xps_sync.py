"""XPS Intelligence sync service.

Exports normalized lead data as structured JSON for GitHub Pages and
dispatches update events to the XPS Intelligence Frontend repo.

Authentication
--------------
Two authentication strategies are supported (GitHub App is preferred):

1. **GitHub App** (recommended) – Supply ``app_id`` and ``private_key``.
   The ``installation_id`` is optional: when omitted the service auto-discovers
   the installation by querying ``GET /orgs/{org}/installation``, which works
   for Apps installed org-wide (the common case for InfinityXOneSystems).

2. **PAT fallback** – Supply a ``github_token`` (Personal Access Token).
   Used only when GitHub App credentials are not configured or when all App
   auth paths fail.
"""
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from .github_app_auth import GitHubAppAuth
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
        # GitHub App credentials (preferred over PAT)
        app_id: str = "",
        private_key: str = "",
        installation_id: str = "",
    ):
        self.github_token = github_token
        self.xps_system_repo = xps_system_repo
        self.xps_frontend_repo = xps_frontend_repo
        self.pages_branch = pages_branch
        self.app_id = app_id
        self.private_key = private_key
        self.installation_id = installation_id
        self._last_sync_at: Optional[datetime] = None
        self._last_sync_status: str = "never"
        self._last_sync_counts: Dict[str, int] = {}

    # ------------------------------------------------------------------
    # Token resolution
    # ------------------------------------------------------------------

    def _resolve_token(self) -> str:
        """Return the best available authentication token.

        Resolution order:
        1. GitHub App installation token using the explicit ``installation_id``
           when it is configured.
        2. GitHub App installation token after auto-discovering the installation
           ID from the org (``GET /orgs/{org}/installation``).  This works for
           App installations scoped to an entire organization.
        3. Plain ``github_token`` (PAT) fallback when neither App path succeeds.

        Returns an empty string if no auth is available.
        """
        if not GitHubAppAuth.is_configured(self.app_id, self.private_key):
            return self.github_token

        auth = GitHubAppAuth(app_id=self.app_id, private_key=self.private_key)

        # Resolve the installation ID – use explicit value or auto-discover.
        installation_id = self.installation_id
        if not installation_id:
            org = self.xps_system_repo.split("/")[0] if "/" in self.xps_system_repo else ""
            if org:
                try:
                    installation_id = auth.get_org_installation_id(org)
                except (RuntimeError, ValueError) as exc:
                    logger.error(
                        f"GitHub App installation ID auto-discovery failed "
                        f"for org '{org}': {exc} – falling back to PAT"
                    )
                    return self.github_token
            else:
                logger.warning(
                    "GitHub App credentials present but installation_id is not "
                    "set and org cannot be determined – falling back to PAT"
                )
                return self.github_token

        try:
            return auth.get_installation_token(installation_id)
        except (RuntimeError, ValueError) as exc:
            logger.error(
                f"GitHub App token generation failed: {exc} – "
                "falling back to PAT"
            )
            return self.github_token

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

        Authentication uses the GitHub App when configured; falls back to PAT.
        """
        token = self._resolve_token()
        if not token:
            logger.warning(
                "No GitHub auth configured (App or PAT) – skipping frontend dispatch"
            )
            return {"success": False, "reason": "no_token"}

        url = f"https://api.github.com/repos/{self.xps_frontend_repo}/dispatches"
        headers = {
            "Authorization": f"Bearer {token}",
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
