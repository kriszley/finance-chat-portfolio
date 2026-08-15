"""File upload endpoint. POST /api/upload saves CSV and validates bank format."""

import re
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, UploadFile, File, HTTPException

from db.models import UploadResponse
from scripts.config_paths import accounts_config_path

import yaml

router = APIRouter(prefix="/api", tags=["upload"])

UPLOAD_DIR = Path(__file__).parent.parent / "data" / "uploads"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def _match_account(filename: str, accounts: dict) -> Optional[str]:
    filename_lower = filename.lower()
    for account_name in accounts:
        if account_name.lower().replace("-", "").replace("_", "") in \
                filename_lower.replace("-", "").replace("_", ""):
            return account_name
    for account_name, account in accounts.items():
        institution = account.get("institution", "").lower()
        if institution and institution in filename_lower:
            return account_name
    return None


@router.post("/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)):
    original_name = (file.filename or "").replace("\\", "/").rsplit("/", 1)[-1]
    if not original_name or not original_name.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", original_name).strip("._")
    if not safe_name.lower().endswith(".csv"):
        safe_name = f"upload-{uuid.uuid4().hex}.csv"
    stored_name = f"{uuid.uuid4().hex}-{safe_name}"
    file_path = (UPLOAD_DIR / stored_name).resolve()

    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="CSV file exceeds the 10 MiB limit")
    with open(file_path, "wb") as f:
        f.write(content)

    # Detect bank
    detected_bank = None
    try:
        with open(accounts_config_path(), encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        accounts = {a["name"]: a for a in cfg.get("accounts", [])}
        account_name = _match_account(original_name, accounts)
        if account_name:
            detected_bank = accounts[account_name].get("institution")
    except Exception:
        pass

    return UploadResponse(
        filename=original_name,
        # This is an opaque upload token, not an arbitrary filesystem path.
        file_path=stored_name,
        detected_bank=detected_bank,
    )
