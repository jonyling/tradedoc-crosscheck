"""Tiny keyword-based HS code suggester. Output is ALWAYS a suggestion for a broker to confirm."""
from typing import Optional

from .schemas import HSSuggestion

# (keywords, HS 6-digit, description) - small illustrative table, not a tariff database
_TABLE = [
    (("flow meter", "flowmeter", "flow transmitter"), "9026.10", "Instruments for measuring flow or level of liquids"),
    (("pressure transmitter", "pressure gauge"), "9026.20", "Instruments for measuring pressure"),
    (("valve",), "8481.80", "Taps, cocks, valves and similar appliances"),
    (("pump",), "8413.70", "Other centrifugal pumps"),
    (("cable", "wire"), "8544.49", "Electric conductors, voltage <= 1000 V"),
    (("sensor", "temperature"), "9025.19", "Thermometers / temperature sensors"),
]


def suggest_hs(description: Optional[str]) -> Optional[HSSuggestion]:
    if not description:
        return None
    text = description.lower()
    for keywords, code, desc in _TABLE:
        hit = next((k for k in keywords if k in text), None)
        if hit:
            return HSSuggestion(code=code, description=desc, basis=f"keyword '{hit}' in goods description")
    return None
