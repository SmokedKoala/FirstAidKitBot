"""HTTP API: POST an image, receive decoded barcodes and Medum.ru data for EAN-13."""

import os

import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile

import main as core

app = FastAPI(
    title="FirstAidKitBot",
    description=(
        "Upload an image containing barcodes. EAN-13 codes are resolved against "
        "[Medum.ru](https://medum.ru/). Reference only, not medical advice."
    ),
    version="1.0.0",
)


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "FirstAidKitBot", "docs": "/docs", "health": "/health"}


def _result_from_bytes(data: bytes) -> dict:
    result = core.scan_image_bytes(data)
    if err := result.get("error"):
        if err == "empty_body":
            raise HTTPException(status_code=400, detail="Empty file body.")
        if err == "invalid_or_unsupported_image":
            raise HTTPException(
                status_code=400,
                detail="Could not decode image. Use a supported format (e.g. JPEG, PNG).",
            )
        raise HTTPException(status_code=400, detail=err)
    return result


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/scan")
async def scan(file: UploadFile = File(..., description="Image file (JPEG, PNG, etc.)")) -> dict:
    """
    Decode barcodes from the uploaded image.

    Returns `barcodes`: list of `{ data, symbology, rect, medum?, medum_url?, medum_note? }`.
    """
    data = await file.read()
    return _result_from_bytes(data)


def start() -> None:
    """Run the HTTP server (listens for incoming requests).

    Default bind is 127.0.0.1 so http://127.0.0.1:PORT matches the listener.
    On Windows, http://localhost can use IPv6 (::1) while the server may only
    be on IPv4, which can produce connection errors — use 127.0.0.1 or set
    HOST=0.0.0.0 and connect via your LAN IP as needed.
    """
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    reload = os.environ.get("RELOAD", "").lower() in ("1", "true", "yes")
    # Passing `app` directly (no reload) avoids extra import/subprocess issues on Windows.
    if reload:
        uvicorn.run(
            "app:app",
            host=host,
            port=port,
            reload=True,
            log_level="info",
        )
    else:
        uvicorn.run(
            app,
            host=host,
            port=port,
            reload=False,
            log_level="info",
        )


if __name__ == "__main__":
    start()
