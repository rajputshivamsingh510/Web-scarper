"""Lead-level validation. We only claim what we actually checked."""
from __future__ import annotations

from .models import Lead
from .normalize import normalize_phone

NOT_VERIFIED = "ownership_and_active_status_not_verified"


def finalize(lead: Lead) -> Lead:
    """Set phone_status / verification_status. Format checks only - never 'active'."""
    if lead.phone:
        lead.phone, lead.phone_status = normalize_phone(lead.phone)
        if not lead.phone:
            lead.phone_status = "invalid_format"
    else:
        lead.phone_status = "missing"
    if not lead.website_status:
        lead.website_status = "missing" if not lead.website else "not_checked"
    lead.verification_status = f"phone:{lead.phone_status}; website:{lead.website_status}; {NOT_VERIFIED}"
    return lead


INVALID_URL_STATUSES = ("unreachable", "error_")


def is_invalid_url_status(status: str) -> bool:
    return status == "unreachable" or status.startswith("error_")


def was_checked(status: str) -> bool:
    return status in ("reachable", "unreachable", "robots_disallowed") or status.startswith("error_")
