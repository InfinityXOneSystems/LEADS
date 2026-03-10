"""Automated email outreach service."""
from datetime import datetime
from typing import Optional, Dict, Any, List
from ..utils.logger import get_logger

logger = get_logger(__name__)

INITIAL_EMAIL_SUBJECT = "Epoxy Contractors: AI Tool for Qualified Leads + Free Training"

EMAIL_TEMPLATE = """Hi {decision_maker_name},

I noticed {company_name} specializes in {specializations}.

We just launched something special for epoxy contractors:

THE FIRST AI APP DEDICATED TO EPOXY CONTRACTORS

- Qualified Leads - AI finds buyers in your market
- AI Takeoff - Measure square footage from photos
- Proposal Generator - Auto-create proposals in 60 seconds
- Billing Automation - Stripe integration, invoices
- Educational Videos - Learn epoxy industry secrets
- Discounted Materials - 20% off epoxy, supplies
- Training Classes - Online certification courses
- Marketing AI Partner - Manage Facebook & SEO
- CRM Integration - Track all your leads & projects

Built by Xtreme Polishing Systems
The U.S.'s largest and most trusted epoxy manufacturer.

LIMITED TIME: First month FREE (normally $50/month)

Claim your free trial:
{onboard_url}

Questions? Reply to this email or call us at 1-800-XPS-LEAD.

Best,
XPS Intelligence Team
Xtreme Polishing Systems
"""


class EmailOutreachService:
    """Manages automated email campaigns for leads."""

    def __init__(self, smtp_host: str = "", smtp_port: int = 587,
                 smtp_user: str = "", smtp_password: str = "",
                 from_email: str = "noreply@xps-intelligence.com",
                 from_name: str = "XPS Intelligence Team",
                 frontend_url: str = "https://xps-intelligence.com"):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.from_email = from_email
        self.from_name = from_name
        self.frontend_url = frontend_url

    def send_initial_email(self, lead_id: str, to_email: str,
                            decision_maker_name: str,
                            company_name: str,
                            specializations: List[str]) -> Dict[str, Any]:
        """Send initial outreach email."""
        if not to_email:
            return {"success": False, "error": "no_email"}

        spec_text = ", ".join(specializations[:3]) if specializations else "concrete work"
        name = decision_maker_name or "there"
        onboard_url = f"{self.frontend_url}/onboard?lead_id={lead_id}"

        body = EMAIL_TEMPLATE.format(
            decision_maker_name=name,
            company_name=company_name,
            specializations=spec_text,
            onboard_url=onboard_url,
        )

        result = self._send_email(
            to_email=to_email,
            subject=INITIAL_EMAIL_SUBJECT,
            body=body,
        )

        if result["success"]:
            logger.info(f"Initial email sent to {to_email} for lead {lead_id}")
        else:
            logger.warning(f"Email send failed for lead {lead_id}: {result.get('error')}")

        return result

    def send_follow_up_email(self, lead_id: str, to_email: str,
                              decision_maker_name: str,
                              company_name: str,
                              follow_up_number: int = 1) -> Dict[str, Any]:
        """Send follow-up email."""
        name = decision_maker_name or "there"
        onboard_url = f"{self.frontend_url}/onboard?lead_id={lead_id}"

        subject = f"Re: XPS Intelligence - {company_name}"
        body = (
            f"Hi {name},\n\n"
            f"Just following up on my previous email about XPS Intelligence "
            f"for {company_name}.\n\n"
            f"Our AI platform helps epoxy contractors like you find qualified "
            f"leads, automate proposals, and grow faster.\n\n"
            f"First month is still FREE: {onboard_url}\n\n"
            f"Best,\nXPS Intelligence Team"
        )

        return self._send_email(to_email=to_email, subject=subject, body=body)

    def _send_email(self, to_email: str, subject: str,
                    body: str) -> Dict[str, Any]:
        """Internal email send method."""
        if not self.smtp_host or not self.smtp_user:
            logger.debug("SMTP not configured, email not sent (dry run)")
            return {
                "success": True,
                "dry_run": True,
                "to": to_email,
                "subject": subject,
            }

        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            msg = MIMEMultipart()
            msg["From"] = f"{self.from_name} <{self.from_email}>"
            msg["To"] = to_email
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.ehlo()
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.from_email, to_email, msg.as_string())

            return {"success": True, "to": to_email, "subject": subject}
        except Exception as e:
            logger.error(f"Email send error: {e}")
            return {"success": False, "error": str(e)}
