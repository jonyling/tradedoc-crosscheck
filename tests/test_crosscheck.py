from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.crosscheck import crosscheck, weight_equal
from app.main import app
from app.schemas import BillOfLading, CommercialInvoice, Severity, Status

SAMPLES = Path(__file__).parent.parent / "samples"
BASE = dict(shipper="Lionsgate Instruments Pte Ltd", consignee="Hollandse Procestechniek B.V.",
            container_number="DEMU1234565", package_count=24, gross_weight_kg=1850.0,
            port_of_loading="Singapore (SGSIN)", port_of_discharge="Rotterdam (NLRTM)",
            goods_description="Flow meters")
HIGH = {k: 0.95 for k in BASE}


def pair(inv_over=None, bl_over=None, conf=HIGH):
    inv = CommercialInvoice(**{**BASE, **(inv_over or {})}, confidence=conf)
    bl = BillOfLading(**{**BASE, **(bl_over or {})}, confidence=conf)
    return crosscheck(inv, bl)


def by_field(result):
    return {c.field: c for c in result.comparisons}


def test_clean_pair_all_match():
    r = pair()
    assert r.summary["mismatch"] == 0 and r.summary["missing"] == 0
    assert not r.needs_human_review


@pytest.mark.parametrize("field,bad", [
    ("container_number", "DEMU1234556"), ("package_count", 22),
    ("gross_weight_kg", 1925.0), ("consignee", "Hollandse Prosestechniek B.V."),
])
def test_high_severity_mismatches(field, bad):
    c = by_field(pair(bl_over={field: bad}))[field]
    assert c.status == Status.mismatch and c.severity == Severity.high and c.needs_human_review


def test_case_and_punctuation_ignored():
    assert by_field(pair(bl_over={"consignee": "HOLLANDSE PROCESTECHNIEK BV"}))["consignee"].status == Status.match


def test_typo_hint():
    assert "typo" in by_field(pair(bl_over={"consignee": "Hollandse Prosestechniek B.V."}))["consignee"].note


def test_weight_tolerance():
    assert weight_equal(1850.0, 1853.0)[0]      # within 0.5%
    assert not weight_equal(1850.0, 1925.0)[0]


def test_missing_field_flagged():
    c = by_field(pair(bl_over={"container_number": None}))["container_number"]
    assert c.status == Status.missing and c.needs_human_review


def test_low_confidence_match_needs_review():
    r = pair(conf={**HIGH, "consignee": 0.6})
    c = by_field(r)["consignee"]
    assert c.status == Status.match and c.needs_human_review and r.needs_human_review


def test_end_to_end_mismatch_samples():
    client = TestClient(app)
    files = {"invoice": open(SAMPLES / "mismatch_invoice.pdf", "rb"),
             "bill_of_lading": open(SAMPLES / "mismatch_bl.pdf", "rb")}
    r = client.post("/crosscheck", files=files).json()
    bad = {c["field"] for c in r["comparisons"] if c["status"] == "mismatch"}
    assert bad == {"consignee", "container_number", "package_count", "gross_weight_kg"}
    assert r["invoice"]["hs_code_suggestion"]["is_suggestion"] is True


def test_end_to_end_clean_samples():
    client = TestClient(app)
    files = {"invoice": open(SAMPLES / "clean_invoice.pdf", "rb"),
             "bill_of_lading": open(SAMPLES / "clean_bl.pdf", "rb")}
    assert client.post("/crosscheck", files=files).json()["needs_human_review"] is False


def test_extract_invoice_fields():
    client = TestClient(app)
    d = client.post("/extract", files={"file": open(SAMPLES / "clean_invoice.pdf", "rb")}).json()
    assert d["invoice_number"] == "LGI-INV-2026-0418" and d["total_value"] == 104800.0
    assert len(d["line_items"]) == 3


def test_rejects_non_pdf():
    client = TestClient(app)
    assert client.post("/extract", files={"file": ("x.txt", b"hello")}).status_code == 400


# ---------- xAI provider (mocked, no network/key needed) ----------
import json as _json

from app import extract as ex


def _text():
    return ex.pdf_to_text((SAMPLES / "clean_bl.pdf").read_bytes())


def test_no_key_uses_regex(monkeypatch):
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    assert ex.extract((SAMPLES / "clean_bl.pdf").read_bytes()).extraction_method == "regex"


def test_xai_result_used_when_key_set(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "test")
    monkeypatch.setattr(ex, "_call_xai", lambda p, k: _json.dumps(
        {"bl_number": "X1", "package_count": 24, "confidence": {"bl_number": 0.9}}))
    doc = ex.llm_extract(_text(), "bill_of_lading")
    assert doc.bl_number == "X1" and doc.extraction_method.startswith("xai:")


def test_xai_bad_json_falls_back(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "test")
    monkeypatch.setattr(ex, "_call_xai", lambda p, k: "not json")
    doc = ex.extract((SAMPLES / "clean_bl.pdf").read_bytes(), "bill_of_lading")
    assert doc.extraction_method == "regex" and doc.bl_number == "OCNX-SIN-RTM-77310"
