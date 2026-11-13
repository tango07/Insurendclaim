"""Structured request/response contracts for AI claim guidance."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

DISCLAIMER = (
    "AI-generated guidance based on fictional sample policy data. This is not a coverage decision, "
    "claim approval, damage valuation or fraud assessment. A claims adjuster makes all decisions."
)


# ----- What we send to the model (only what's relevant; no name, no profile data) -----
class CoverageCtx(BaseModel):
    code: str
    name: str
    description: str
    limit_note: Optional[str] = None
    deductible_amount: Optional[float] = None


class ClauseCtx(BaseModel):
    code: str
    text: str


class PolicyContext(BaseModel):
    policy_type: str
    product_name: str
    policy_status: str
    wording_available: bool
    asset_type: str
    asset_name: str
    coverages: list[CoverageCtx]
    exclusions: list[ClauseCtx]
    conditions: list[ClauseCtx]
    allowed_categories: dict[str, str]  # key -> label


class AttachmentMeta(BaseModel):
    filename: str
    content_type: str
    size_bytes: int
    text_excerpt: Optional[str] = None  # only for plain-text documents
    analysed: bool = False               # image was sent to the vision model


class GuidanceRequest(BaseModel):
    description: str
    incident_date: Optional[str] = None
    incident_location: Optional[str] = None
    policy: PolicyContext
    attachments: list[AttachmentMeta] = []
    answered_keys: list[str] = []  # follow-up topics the user already answered in chat


# ----- What the model must return (validated strictly) -----
class CoverageRef(BaseModel):
    coverage_code: str
    why_relevant: str = Field(max_length=400)


class ExclusionRef(BaseModel):
    code: str
    why_relevant: str = Field(max_length=400)


class ImageObservation(BaseModel):
    filename: str
    observation: str = Field(min_length=3, max_length=600)
    matches_description: Literal["yes", "partly", "no", "unclear"] = "unclear"


class ModelGuidance(BaseModel):
    suggested_category: str
    category_confidence: Literal["low", "medium", "high"]
    incident_summary: str = Field(min_length=10, max_length=800)
    relevant_coverages: list[CoverageRef] = Field(default_factory=list, max_length=8)
    possible_exclusions: list[ExclusionRef] = Field(default_factory=list, max_length=8)
    missing_information: list[str] = Field(default_factory=list, max_length=12)
    documents_to_collect: list[str] = Field(default_factory=list, max_length=12)
    next_steps: list[str] = Field(default_factory=list, min_length=1, max_length=10)
    limitations: list[str] = Field(default_factory=list, max_length=8)
    needs_adjuster_review: bool = False
    image_observations: list[ImageObservation] = Field(default_factory=list, max_length=10)


# ----- What the UI receives: model output grounded + enriched with policy facts -----
class CoverageInsight(BaseModel):
    coverage_code: str
    coverage_name: str
    why_relevant: str
    policy_wording: str
    limit_note: Optional[str] = None
    deductible_amount: Optional[float] = None


class ExclusionInsight(BaseModel):
    code: str
    policy_wording: str
    why_relevant: str


class ClaimGuidance(BaseModel):
    suggested_category: str
    suggested_category_label: str
    category_confidence: Literal["low", "medium", "high"]
    incident_summary: str
    relevant_coverages: list[CoverageInsight]
    possible_exclusions: list[ExclusionInsight]
    missing_information: list[str]
    documents_to_collect: list[str]
    next_steps: list[str]
    limitations: list[str]
    needs_adjuster_review: bool
    attachment_notes: list[str]
    image_observations: list[ImageObservation] = []
    provider: str                     # mock | anthropic | openai
    fallback_reason: Optional[str] = None
    disclaimer: str = DISCLAIMER
