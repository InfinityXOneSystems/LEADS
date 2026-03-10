"""Data validation pipeline."""
from typing import Dict, Any, List, Tuple
from ..models.lead import Lead
from ..utils.validators import PhoneValidator, EmailValidator, AddressValidator
from ..utils.logger import get_logger

logger = get_logger(__name__)

EXCLUDED_INDUSTRIES = {"personal", "hobby", "retired", "non-profit"}


class ValidationPipeline:
    """Validates lead data against defined rules."""

    def validate(self, lead: Lead) -> Tuple[Lead, Dict[str, Any]]:
        """Run all validation rules on a lead."""
        issues = []
        warnings = []
        blocked_reasons = []

        # Company name validation
        if not lead.company.name or len(lead.company.name.strip()) < 2:
            issues.append("company_name: required, min 2 characters")
            blocked_reasons.append("missing_company_name")
        elif len(lead.company.name) > 255:
            issues.append("company_name: exceeds 255 characters")

        # Phone validation
        phone = lead.primary_contact.phone or lead.company.phone
        if not phone:
            issues.append("phone: required")
        elif not PhoneValidator.is_valid(phone):
            issues.append(f"phone: invalid format ({phone})")

        # Email validation
        if not lead.primary_contact.email:
            warnings.append("email: not provided")
        elif not EmailValidator.is_valid(lead.primary_contact.email):
            issues.append(f"email: invalid format ({lead.primary_contact.email})")

        # Address validation
        if not lead.company.address:
            warnings.append("address: not provided")
        elif not AddressValidator.is_valid(lead.company.address):
            issues.append(f"address: invalid ({lead.company.address})")

        # Industry validation
        if lead.company.industry:
            industry_lower = lead.company.industry.lower()
            if any(excl in industry_lower for excl in EXCLUDED_INDUSTRIES):
                blocked_reasons.append("excluded_industry")
                issues.append(f"industry: excluded category ({lead.company.industry})")

        # Calculate completeness
        completeness = self._calculate_completeness(lead)

        is_valid = len(issues) == 0 and len(blocked_reasons) == 0
        validation_status = "valid" if is_valid else ("invalid" if blocked_reasons else "partial")

        # Update lead data quality
        lead.data_quality.completeness_score = completeness
        lead.data_quality.validation_status = validation_status
        lead.data_quality.missing_fields = self._get_missing_fields(lead)
        lead.data_quality.flagged_issues = issues + warnings

        result = {
            "is_valid": is_valid,
            "issues": issues,
            "warnings": warnings,
            "blocked_reasons": blocked_reasons,
            "completeness_score": completeness,
            "validation_status": validation_status,
        }
        logger.info(
            f"Lead {lead.id} validation: {validation_status} "
            f"(issues={len(issues)}, warnings={len(warnings)})"
        )
        return lead, result

    def _calculate_completeness(self, lead: Lead) -> float:
        """Calculate data completeness as 0.0-1.0."""
        fields_to_check = [
            bool(lead.company.name),
            bool(lead.company.phone or lead.primary_contact.phone),
            bool(lead.primary_contact.email),
            bool(lead.company.address),
            bool(lead.company.city),
            bool(lead.company.state),
            bool(lead.company.website),
            bool(lead.primary_contact.name),
            bool(lead.company.industry),
            bool(lead.company.business_status),
        ]
        filled = sum(1 for f in fields_to_check if f)
        return round(filled / len(fields_to_check), 2)

    def _get_missing_fields(self, lead: Lead) -> List[str]:
        """Return list of missing required/important fields."""
        missing = []
        if not lead.company.name:
            missing.append("company.name")
        if not (lead.company.phone or lead.primary_contact.phone):
            missing.append("phone")
        if not lead.primary_contact.email:
            missing.append("primary_contact.email")
        if not lead.company.address:
            missing.append("company.address")
        if not lead.company.city:
            missing.append("company.city")
        if not lead.company.state:
            missing.append("company.state")
        if not lead.company.website:
            missing.append("company.website")
        if not lead.primary_contact.name:
            missing.append("primary_contact.name")
        return missing
