"""FastAPI app: /extract, /crosscheck and a single-page UI."""
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from .crosscheck import crosscheck
from .extract import extract
from .schemas import BillOfLading, CommercialInvoice, CrossCheckResult

STATIC = Path(__file__).parent / "static"
app = FastAPI(title="TradeDoc CrossCheck", version="0.1.0")


async def _read_pdf(f: UploadFile) -> bytes:
    data = await f.read()
    if not data.startswith(b"%PDF"):
        raise HTTPException(400, f"{f.filename} is not a PDF")
    return data


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/extract")
async def extract_endpoint(file: UploadFile = File(...),
                           doc_type: Optional[str] = Query(None, pattern="^(commercial_invoice|bill_of_lading)$")):
    return extract(await _read_pdf(file), doc_type)


@app.post("/crosscheck", response_model=CrossCheckResult)
async def crosscheck_endpoint(invoice: UploadFile = File(...), bill_of_lading: UploadFile = File(...)):
    inv = extract(await _read_pdf(invoice), "commercial_invoice")
    bl = extract(await _read_pdf(bill_of_lading), "bill_of_lading")
    assert isinstance(inv, CommercialInvoice) and isinstance(bl, BillOfLading)
    return crosscheck(inv, bl)
