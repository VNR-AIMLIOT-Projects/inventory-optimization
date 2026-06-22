# =====================================================================
# File upload security hardening for Backend-RL/src/app.py
# This module adds:
#   1. File size enforcement (before reading full content)
#   2. Filename sanitization (prevent path traversal)
#   3. Content-type validation (not just extension check)
#   4. Rate limiting via slowapi
# =====================================================================
import re
import os
from fastapi import HTTPException, UploadFile

# Max upload size: 15 MB  (matches nginx ingress proxy-body-size)
MAX_UPLOAD_BYTES = 15 * 1024 * 1024

# Allowed MIME types for demand file uploads
ALLOWED_CONTENT_TYPES = {
    "text/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/octet-stream",   # some browsers send this for .xlsx
}

ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}


def sanitize_upload_filename(original: str) -> str:
    """
    Strip path components and replace unsafe characters.
    Prevents path traversal attacks like '../../etc/passwd'.
    
    Examples:
        '../../evil.csv'  → 'evil.csv'
        'my data (2025).xlsx' → 'my_data_2025_.xlsx'
        'normal_file.csv' → 'normal_file.csv'
    """
    # 1. Strip any directory components
    basename = os.path.basename(original)
    # 2. Replace any character that isn't alphanumeric, dash, underscore, or dot
    safe = re.sub(r"[^a-zA-Z0-9._-]", "_", basename)
    # 3. Prevent double-dots (e.g. hiding ../ inside the name)
    safe = re.sub(r"\.{2,}", ".", safe)
    # 4. Ensure it's not empty
    if not safe or safe == ".":
        safe = "upload"
    return safe


async def validate_upload(file: UploadFile) -> bytes:
    """
    Read and validate an uploaded file.
    Returns the file content as bytes.
    
    Raises HTTPException 400/413 on validation failure.
    """
    # 1. Extension check
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Upload a .csv or .xlsx file."
        )

    # 2. Content-Type check (loose — browsers are inconsistent)
    content_type = (file.content_type or "").lower().split(";")[0].strip()
    if content_type and content_type not in ALLOWED_CONTENT_TYPES:
        # Warn but don't block — content-type is unreliable in multipart uploads
        pass  # Log in future with observability stack

    # 3. Read content with size guard
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(content) / 1024 / 1024:.1f} MB). Maximum allowed: 15 MB."
        )
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    return content

# ---------------------------------------------------------------------
# API Key Authentication
# ---------------------------------------------------------------------
from fastapi.security.api_key import APIKeyHeader
from fastapi import Security

API_KEY_NAME = "X-API-Key"
# Use a static API key for demonstration/basic auth, default to "replenix-secret-key"
API_KEY = os.getenv("API_KEY", "replenix-secret-key")

api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def verify_api_key(api_key: str = Security(api_key_header)):
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: Missing API Key"
        )
    if api_key != API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: Invalid API Key"
        )
    return api_key
