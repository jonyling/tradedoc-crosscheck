"""Document extraction: xAI Grok first (XAI_API_KEY), deterministic regex fallback."""
import io
import json
import logging
import os
import re
from typing import Optional, Type, Union

import httpx
import pdfplumber
from pydantic import BaseModel, ValidationError

from .hs import suggest_hs
from .schemas import BillOfLading, CommercialInvoice, LineItem

log = logging.getLogger(__name__)
Doc = Union[CommercialInvoice, BillOfLading]


# ---------- text ----------
def pdf_to_text(data: bytes) -> str:
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def detect_doc_type(text: str) -> str:
    t = text.lower()
    if "bill of lading" in t or "b/l no" in t:
        return "bill_of_lading"
    return "commercial_invoice"


# ---------- regex fallback ----------
def _field(text: str, *labels: str) -> Optional[str]:
    for label in labels:
        m = re.search(rf"^{label}\s*:\s*(.+)$", text, re.IGNORECASE | re.MULTILINE)
        if m:
            return m.group(1).strip()
    return None


def _number(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    m = re.search(r"[\d,]+(?:\.\d+)?", value)
    return float(m.group(0).replace(",", "")) if m else None


def _container(text: str) -> Optional[str]:
    m = re.search(r"\b([A-Z]{4}\d{7})\b", text)  # ISO 6346 shape
    return m.group(1) if m else None


def regex_extract(text: str, doc_type: str) -> Doc:
    common = dict(
        shipper=_field(text, "Shipper"),
        consignee=_field(text, "Consignee"),
        port_of_loading=_field(text, "Port of Loading"),
        port_of_discharge=_field(text, "Port of Discharge"),
        container_number=_container(text),
        goods_description=_field(text, "Description of Goods"),
        gross_weight_kg=_number(_field(text, "Gross Weight")),
    )
    pk = _number(_field(text, "Packages", "No. of Packages"))
    common["package_count"] = int(pk) if pk is not None else None

    if doc_type == "bill_of_lading":
        doc: Doc = BillOfLading(
            **common,
            bl_number=_field(text, r"B/L No"),
            notify_party=_field(text, "Notify Party"),
            vessel_voyage=_field(text, r"Vessel / Voyage", "Vessel"),
            seal_number=_field(text, "Seal No"),
        )
    else:
        total = _field(text, "Total Value")
        cur = re.search(r"\b([A-Z]{3})\b", total or "")
        items = [
            LineItem(description=m.group(1).strip(), quantity=float(m.group(2)),
                     unit_price=float(m.group(3).replace(",", "")), amount=float(m.group(4).replace(",", "")))
            for m in re.finditer(r"^(.+?)\s+(\d+)\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})$", text, re.MULTILINE)
        ]
        doc = CommercialInvoice(
            **common,
            invoice_number=_field(text, "Invoice No"),
            invoice_date=_field(text, "Invoice Date"),
            incoterms=_field(text, "Incoterms"),
            currency=cur.group(1) if cur else None,
            total_value=_number(total),
            net_weight_kg=_number(_field(text, "Net Weight")),
            country_of_origin=_field(text, "Country of Origin"),
            line_items=items,
        )
    # Regex is exact when a labelled field is present; unlabelled = no confidence.
    doc.confidence = {k: (0.95 if v not in (None, [], "") else 0.0)
                      for k, v in doc.model_dump(exclude={"confidence", "extraction_method", "doc_type",
                                                          "hs_code_suggestion", "line_items"}).items()}
    doc.extraction_method = "regex"
    return doc


# ---------- LLM ----------
def _prompt(text: str, model: Type[BaseModel]) -> str:
    schema = {k: v for k, v in model.model_json_schema().items() if k in ("properties", "$defs")}
    return (
        "You extract fields from a freight/trade document. Return ONLY JSON matching this schema. "
        "Use null for anything not present; never guess. Weights in kg. Also include a 'confidence' "
        "object mapping each field name to a 0-1 score.\n"
        f"SCHEMA: {json.dumps(schema)}\n\nDOCUMENT TEXT:\n{text[:15000]}"
    )


XAI_BASE_URL = os.getenv("XAI_BASE_URL", "https://api.x.ai/v1")
XAI_MODEL = os.getenv("XAI_MODEL", "grok-4.3")


def _call_xai(prompt: str, key: str) -> str:
    """xAI Grok via its OpenAI-compatible Chat Completions endpoint, JSON output."""
    body = {"model": XAI_MODEL, "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": "You are a precise trade-document extraction engine."},
                         {"role": "user", "content": prompt}]}
    effort = os.getenv("XAI_REASONING_EFFORT", "none")  # grok-4.3: none|low|medium|high; "" to omit
    if effort:
        body["reasoning_effort"] = effort
    r = httpx.post(f"{XAI_BASE_URL}/chat/completions", json=body, timeout=60,
                   headers={"Authorization": f"Bearer {key}"})
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def llm_extract(text: str, doc_type: str) -> Optional[Doc]:
    """Send the PDF's extracted text (not the PDF itself) to Grok. None => caller uses regex."""
    key = os.getenv("XAI_API_KEY")
    if not key:
        return None
    model = BillOfLading if doc_type == "bill_of_lading" else CommercialInvoice
    try:
        raw = json.loads(_call_xai(_prompt(text, model), key))
        raw.pop("doc_type", None)
        doc = model.model_validate(raw)
        doc.extraction_method = f"xai:{XAI_MODEL}"
        return doc
    except (httpx.HTTPError, ValueError, KeyError, ValidationError) as e:
        log.warning("xAI extraction failed, falling back to regex: %s", e)
        return None


# ---------- entry point ----------
def extract(data: bytes, doc_type: Optional[str] = None) -> Doc:
    text = pdf_to_text(data)
    doc_type = doc_type or detect_doc_type(text)
    doc = llm_extract(text, doc_type) or regex_extract(text, doc_type)
    doc.hs_code_suggestion = suggest_hs(doc.goods_description)
    return doc
