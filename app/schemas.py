"""Pydantic schemas for extracted trade documents and cross-check results."""
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class LineItem(BaseModel):
    description: str
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    amount: Optional[float] = None


class HSSuggestion(BaseModel):
    code: str
    description: str
    is_suggestion: bool = True  # always a suggestion: a broker must confirm
    basis: str = "keyword match on goods description"


class CommercialInvoice(BaseModel):
    doc_type: str = "commercial_invoice"
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    shipper: Optional[str] = None
    consignee: Optional[str] = None
    incoterms: Optional[str] = None
    currency: Optional[str] = None
    total_value: Optional[float] = None
    package_count: Optional[int] = None
    gross_weight_kg: Optional[float] = None
    net_weight_kg: Optional[float] = None
    container_number: Optional[str] = None
    port_of_loading: Optional[str] = None
    port_of_discharge: Optional[str] = None
    country_of_origin: Optional[str] = None
    goods_description: Optional[str] = None
    line_items: list[LineItem] = Field(default_factory=list)
    hs_code_suggestion: Optional[HSSuggestion] = None
    extraction_method: str = "regex"
    confidence: dict[str, float] = Field(default_factory=dict)


class BillOfLading(BaseModel):
    doc_type: str = "bill_of_lading"
    bl_number: Optional[str] = None
    shipper: Optional[str] = None
    consignee: Optional[str] = None
    notify_party: Optional[str] = None
    vessel_voyage: Optional[str] = None
    package_count: Optional[int] = None
    gross_weight_kg: Optional[float] = None
    container_number: Optional[str] = None
    seal_number: Optional[str] = None
    port_of_loading: Optional[str] = None
    port_of_discharge: Optional[str] = None
    goods_description: Optional[str] = None
    hs_code_suggestion: Optional[HSSuggestion] = None
    extraction_method: str = "regex"
    confidence: dict[str, float] = Field(default_factory=dict)


class Status(str, Enum):
    match = "match"
    mismatch = "mismatch"
    missing = "missing"


class Severity(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"
    none = "none"


class FieldComparison(BaseModel):
    field: str
    invoice_value: Optional[str] = None
    bl_value: Optional[str] = None
    status: Status
    severity: Severity
    confidence: float
    needs_human_review: bool
    note: str = ""


class CrossCheckResult(BaseModel):
    comparisons: list[FieldComparison]
    summary: dict[str, int]
    needs_human_review: bool
    invoice: Optional[CommercialInvoice] = None
    bill_of_lading: Optional[BillOfLading] = None
