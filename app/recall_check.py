import json
import uuid
from pathlib import Path

from numpy import block
#from app.main import BASE_DIR
from app.schemas import AuditResult

BASE_DIR = Path(__file__).resolve().parent.parent        # ensure it's a Path object

with open(BASE_DIR / "data" / "rapex_blacklist.json") as f:
    blacklist_data = json.load(f)

blacklist_gtins = {item["barcode"]: item for item in blacklist_data }  # convert to a set for faster lookup
blocked_barcodes = set(blacklist_gtins.keys())

def check_blacklist(gtin: str) -> AuditResult | None:
    if gtin in blocked_barcodes:
        return AuditResult(
            audit_id=str(uuid.uuid4()),
            listing_gtin=gtin,
            verdict="non_compliant",
            risk_type="recalled_product",
            risk_score=1.0,
            violations=["Product barcode matches a known EU Safety Gate recall"],
            pipeline_stage="recall_check",
            reasoning="This GTIN matches a real, recorded product recall.",
        )
    return None