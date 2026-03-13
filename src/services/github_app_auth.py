"""GitHub App authentication helper.

Generates short-lived installation access tokens using a GitHub App's
App ID and RSA private key.  These tokens are equivalent to a PAT but
expire after 1 hour and carry only the permissions granted to the App
installation, making them safer than long-lived personal tokens.

Usage
-----
auth = GitHubAppAuth(app_id="123456", private_key=pem_string)
token = auth.get_installation_token(installation_id="12345678")
# Use ``token`` as a Bearer token in GitHub API calls.
"""
import time
from typing import Optional

import httpx
from jose import jwt

from ..utils.logger import get_logger

logger = get_logger(__name__)

# GitHub requires the JWT to expire within 10 minutes of issue.
_JWT_EXPIRY_SECONDS = 600
# GitHub recommends back-dating the iat by 60 s to handle clock drift.
_JWT_ISSUED_AT_SKEW = 60


def _is_valid_pem_private_key(value: str) -> bool:
    """Return True if *value* looks like a loadable PEM RSA private key.

    Checks for the required header/footer markers *and* attempts to load
    the key bytes with ``cryptography`` to catch truncated or malformed keys
    early.
    """
    if not value:
        return False
    if "-----BEGIN" not in value or "PRIVATE KEY" not in value:
        return False
    if "-----END" not in value:
        return False
    try:
        from cryptography.hazmat.primitives.serialization import load_pem_private_key

        load_pem_private_key(value.encode(), password=None)
        return True
    except Exception:
        return False


class GitHubAppAuth:
    """Generate GitHub App installation access tokens via JWT.

    Parameters
    ----------
    app_id:
        The numeric GitHub App ID shown on the App's settings page.
    private_key:
        PEM-encoded RSA private key (the content of the ``.pem`` file
        downloaded from the GitHub App settings).
    """

    def __init__(self, app_id: str, private_key: str) -> None:
        if not app_id:
            raise ValueError("GitHub App ID must not be empty")
        if not _is_valid_pem_private_key(private_key):
            raise ValueError(
                "private_key must be a PEM-encoded RSA private key string"
            )
        self.app_id = app_id
        self._private_key = private_key

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_jwt(self) -> str:
        """Create a signed JWT valid for up to 10 minutes.

        The JWT is used only to obtain an installation access token; it
        must not be used directly as a GitHub API bearer token.
        """
        now = int(time.time())
        payload = {
            "iat": now - _JWT_ISSUED_AT_SKEW,
            "exp": now + _JWT_EXPIRY_SECONDS,
            "iss": self.app_id,
        }
        token = jwt.encode(payload, self._private_key, algorithm="RS256")
        # python-jose returns str; guard against any future bytes return
        return token if isinstance(token, str) else token.decode()

    def get_installation_token(self, installation_id: str) -> str:
        """Exchange the App JWT for a short-lived installation access token.

        Parameters
        ----------
        installation_id:
            The numeric installation ID.  Use :meth:`get_org_installation_id`
            to discover it automatically for org-wide installations.

        Returns
        -------
        str
            A short-lived Bearer token scoped to the App installation.

        Raises
        ------
        RuntimeError
            If GitHub returns a non-2xx response.
        """
        app_jwt = self.generate_jwt()
        url = (
            f"https://api.github.com/app/installations"
            f"/{installation_id}/access_tokens"
        )
        headers = {
            "Authorization": f"Bearer {app_jwt}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        try:
            with httpx.Client(timeout=15.0) as client:
                response = client.post(url, headers=headers)

            if response.status_code == 201:
                token: str = response.json()["token"]
                logger.info(
                    f"Obtained GitHub App installation token "
                    f"(installation_id={installation_id})"
                )
                return token

            raise RuntimeError(
                f"GitHub App token exchange failed: "
                f"HTTP {response.status_code} – {response.text[:200]}"
            )
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(
                f"GitHub App token exchange error: {exc}"
            ) from exc

    def get_org_installation_id(self, org: str) -> str:
        """Look up the installation ID for an organization using the App JWT.

        Because the App is installed org-wide this call succeeds without
        knowing the installation ID in advance.  The ID returned can then be
        passed to :meth:`get_installation_token`.

        Parameters
        ----------
        org:
            GitHub organization login (e.g. ``"InfinityXOneSystems"``).

        Returns
        -------
        str
            The numeric installation ID as a string.

        Raises
        ------
        RuntimeError
            If GitHub returns a non-2xx response or the response does not
            contain an ``id`` field.
        """
        app_jwt = self.generate_jwt()
        url = f"https://api.github.com/orgs/{org}/installation"
        headers = {
            "Authorization": f"Bearer {app_jwt}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        try:
            with httpx.Client(timeout=15.0) as client:
                response = client.get(url, headers=headers)

            if response.status_code == 200:
                installation_id = str(response.json()["id"])
                logger.info(
                    f"Discovered GitHub App installation ID for org '{org}': "
                    f"{installation_id}"
                )
                return installation_id

            raise RuntimeError(
                f"GitHub App org installation lookup failed for '{org}': "
                f"HTTP {response.status_code} – {response.text[:200]}"
            )
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(
                f"GitHub App org installation lookup error: {exc}"
            ) from exc

    @staticmethod
    def is_configured(
        app_id: Optional[str], private_key: Optional[str]
    ) -> bool:
        """Return True if both App ID and private key are non-empty and valid."""
        return bool(app_id and _is_valid_pem_private_key(private_key or ""))
