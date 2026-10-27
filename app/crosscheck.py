"""Compare a commercial invoice against a bill of lading, field by field."""
import re
from difflib import SequenceMatcher
from typing import Callable, Optional

from .schemas import (BillOfLading, CommercialInvoice, CrossCheckResult, FieldComparison,
                      Severity, Status)

REVIEW_CONFIDENCE = 0.80   # below this, a human must look even if values match
WEIGHT_TOLERANCE = 0.005   # 0.5% - scale rounding between parties


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def text_equal(a: str, b: str) -> tuple[bool, str]:
    if _norm(a) == _norm(b):
        return True, ""
    ratio = SequenceMatcher(None, _norm(a), _norm(b)).ratio()
    hint = " (near-identical: likely a typo)" if ratio > 0.9 else ""
    return False, f"text differs, similarity {ratio:.0%}{hint}"


def exact_equal(a, b) -> tuple[bool, str]:
    return (True, "") if _norm(str(a)) == _norm(str(b)) else (False, "values differ")


def weight_equal(a: float, b: float) -> tuple[bool, str]:
    diff = abs(a - b)
    if diff <= max(a, b) * WEIGHT_TOLERANCE:
        return True, ""
    return False, f"differs by {diff:,.1f} kg ({diff / max(a, b):.1%})"


# field -> (comparator, severity if mismatched). Severity reflects customs impact.
RULES: dict[str, tuple[Callable, Severity]] = {
    "consignee": (text_equal, Severity.high),
    "shipper": (text_equal, Severity.medium),
    "container_number": (exact_equal, Severity.high),
    "package_count": (exact_equal, Severity.high),
    "gross_weight_kg": (weight_equal, Severity.high),
    "port_of_loading": (text_equal, Severity.medium),
    "port_of_discharge": (text_equal, Severity.medium),
    "goods_description": (text_equal, Severity.low),
}


def compare_field(name: str, inv_val, bl_val, confidence: float) -> FieldComparison:
    comparator, mismatch_sev = RULES[name]
    fmt = lambda v: None if v is None else str(v)
    if inv_val in (None, "") or bl_val in (None, ""):
        status, sev, note = Status.missing, Severity.medium, "field absent on one document"
    else:
        ok, note = comparator(inv_val, bl_val)
        status = Status.match if ok else Status.mismatch
        sev = Severity.none if ok else mismatch_sev
    review = status != Status.match or confidence < REVIEW_CONFIDENCE
    if status == Status.match and review:
        note = f"matched, but extraction confidence {confidence:.0%} is low"
    return FieldComparison(field=name, invoice_value=fmt(inv_val), bl_value=fmt(bl_val), status=status,
                           severity=sev, confidence=round(confidence, 2), needs_human_review=review, note=note)


def crosscheck(inv: CommercialInvoice, bl: BillOfLading) -> CrossCheckResult:
    def conf(doc, f) -> float:
        return doc.confidence.get(f, 0.5 if getattr(doc, f) is not None else 0.0)

    comps = [compare_field(f, getattr(inv, f), getattr(bl, f), min(conf(inv, f), conf(bl, f))) for f in RULES]
    summary = {s.value: sum(c.status == s for c in comps) for s in Status}
    summary["needs_review"] = sum(c.needs_human_review for c in comps)
    return CrossCheckResult(comparisons=comps, summary=summary,
                            needs_human_review=any(c.needs_human_review for c in comps),
                            invoice=inv, bill_of_lading=bl)
