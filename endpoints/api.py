"""HTTP API: POST an image, receive decoded barcodes and Medum.ru data for EAN-13."""

import os
from datetime import date, datetime
from typing import Any

import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel
from psycopg2 import IntegrityError

from properties_loader import load_private_properties
from services import first_aid_kits as first_aid_kits_service
from services import medicines as medicines_service
from services import users as users_service
from services.scan_service import scan_image_bytes

load_private_properties()

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
    result = scan_image_bytes(data)
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


class FirstAidKitCreateRequest(BaseModel):
    title: str
    user_ids: list[int] = []


class FirstAidKitResponse(BaseModel):
    id: int
    title: str
    created_at: datetime


class FirstAidKitMedicineCreateRequest(BaseModel):
    name: str
    number_of_drugs: int
    expiration_date: date
    description: str


class FirstAidKitMedicineResponse(BaseModel):
    id: int
    first_aid_kit_id: int
    name: str
    number_of_drugs: int
    expiration_date: date
    description: str


def _ensure_user_found(user: dict[str, Any] | None, user_id: int) -> dict[str, Any]:
    if user is None:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found.")
    return user


def _ensure_first_aid_kit_found(
    first_aid_kit: dict[str, Any] | None, first_aid_kit_id: int
) -> dict[str, Any]:
    if first_aid_kit is None:
        raise HTTPException(
            status_code=404,
            detail=f"First aid kit {first_aid_kit_id} not found.",
        )
    return first_aid_kit


@app.post("/scan")
async def scan(file: UploadFile = File(..., description="Image file (JPEG, PNG, etc.)")) -> dict:
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


@app.post("/first-aid-kits", response_model=FirstAidKitResponse, status_code=201)
def create_first_aid_kit(payload: FirstAidKitCreateRequest) -> dict[str, Any]:
    if not payload.title.strip():
        raise HTTPException(status_code=400, detail="title must not be empty.")
    if not first_aid_kits_service.users_exist(payload.user_ids):
        raise HTTPException(status_code=404, detail="One or more users were not found.")
    return first_aid_kits_service.create_first_aid_kit(
        title=payload.title.strip(),
        user_ids=payload.user_ids,
    )


@app.post(
    "/first-aid-kits/{first_aid_kit_id}/medicines",
    response_model=FirstAidKitMedicineResponse,
    status_code=201,
)
def add_medicine_to_first_aid_kit(
    first_aid_kit_id: int, payload: FirstAidKitMedicineCreateRequest
) -> dict[str, Any]:
    _ensure_first_aid_kit_found(
        first_aid_kits_service.get_first_aid_kit_by_id(first_aid_kit_id),
        first_aid_kit_id,
    )
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="name must not be empty.")
    if payload.number_of_drugs < 0:
        raise HTTPException(status_code=400, detail="number_of_drugs must be >= 0.")
    if not payload.description.strip():
        raise HTTPException(status_code=400, detail="description must not be empty.")
    return first_aid_kits_service.add_medicine_to_first_aid_kit(
        first_aid_kit_id=first_aid_kit_id,
        name=payload.name.strip(),
        number_of_drugs=payload.number_of_drugs,
        expiration_date=payload.expiration_date,
        description=payload.description.strip(),
    )


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
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    reload = os.environ.get("RELOAD", "").lower() in ("1", "true", "yes")
    if reload:
        uvicorn.run(
            "endpoints.api:app",
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

