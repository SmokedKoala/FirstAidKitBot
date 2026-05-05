"""HTTP API: POST an image, receive decoded barcodes and Medum.ru data for EAN-13."""

import os
from datetime import datetime
from typing import Any

from properties_loader import load_private_properties

load_private_properties()

import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel
from psycopg2 import IntegrityError

import medicines as medicines_service
import scan as scan_core
import users as users_service

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
    result = scan_core.scan_image_bytes(data)
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


class UserCreateRequest(BaseModel):
    username: str
    email: str


class UserUpdateRequest(BaseModel):
    username: str | None = None
    email: str | None = None


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    created_at: datetime


class MedicineResponse(BaseModel):
    id: int
    ean13_code: str
    medicine_name: str


def _ensure_user_found(user: dict[str, Any] | None, user_id: int) -> dict[str, Any]:
    if user is None:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found.")
    return user


@app.post("/scan")
async def scan(file: UploadFile = File(..., description="Image file (JPEG, PNG, etc.)")) -> dict:
    """
    Decode barcodes from the uploaded image.

    Returns `barcodes`: list of `{ data, symbology, rect, medum?, medum_url?, medum_note? }`.
    """
    data = await file.read()
    return _result_from_bytes(data)


@app.post("/users", response_model=UserResponse, status_code=201)
def create_user(payload: UserCreateRequest) -> dict[str, Any]:
    try:
        return users_service.create_user(payload.username, payload.email)
    except IntegrityError:
        raise HTTPException(
            status_code=409,
            detail="Username or email already exists.",
        ) from None


@app.get("/users", response_model=list[UserResponse])
def list_users(limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    if limit < 1:
        raise HTTPException(status_code=400, detail="limit must be >= 1.")
    if offset < 0:
        raise HTTPException(status_code=400, detail="offset must be >= 0.")
    return users_service.list_users(limit=limit, offset=offset)


@app.get("/medicines", response_model=list[MedicineResponse])
def list_medicines(limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    if limit < 1:
        raise HTTPException(status_code=400, detail="limit must be >= 1.")
    if offset < 0:
        raise HTTPException(status_code=400, detail="offset must be >= 0.")
    return medicines_service.list_medicines(limit=limit, offset=offset)


@app.get("/users/{user_id}", response_model=UserResponse)
def get_user(user_id: int) -> dict[str, Any]:
    return _ensure_user_found(users_service.get_user_by_id(user_id), user_id)


@app.patch("/users/{user_id}", response_model=UserResponse)
def update_user(user_id: int, payload: UserUpdateRequest) -> dict[str, Any]:
    try:
        user = users_service.update_user(
            user_id=user_id,
            username=payload.username,
            email=payload.email,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except IntegrityError:
        raise HTTPException(
            status_code=409,
            detail="Username or email already exists.",
        ) from None
    return _ensure_user_found(user, user_id)


@app.delete("/users/{user_id}")
def delete_user(user_id: int) -> dict[str, bool]:
    deleted = users_service.delete_user(user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found.")
    return {"deleted": True}


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
