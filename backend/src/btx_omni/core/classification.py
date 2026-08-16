"""Data classification and sensitivity boundaries."""
from __future__ import annotations

from enum import StrEnum


class Classification(StrEnum):
    PUBLIC = "PUBLIC"
    INTERNAL_COMMERCIAL = "INTERNAL_COMMERCIAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    CONTROLLED = "CONTROLLED"
    CUI = "CUI"
    ITAR = "ITAR"
    UNKNOWN_REQUIRES_REVIEW = "UNKNOWN_REQUIRES_REVIEW"


class SensitivityTag(StrEnum):
    CUSTOMER_CONFIDENTIAL = "CUSTOMER_CONFIDENTIAL"
    FINANCIAL = "FINANCIAL"
    PII = "PII"
    DRAWING = "DRAWING"
    CAD = "CAD"
    RESTRICTED_TECHNICAL = "RESTRICTED_TECHNICAL"
