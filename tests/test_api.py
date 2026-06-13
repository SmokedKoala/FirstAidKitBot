"""Tests for the FirstAidKitBot REST API.

Run from the project root:
    pytest tests/
"""
from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pytest
from psycopg2 import IntegrityError

# Ensure project root is importable when running pytest from any cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ── Swap out Telegram lifespan before TestClient starts the app ──────────────
# lifespan() in endpoints.api calls telegram_lifespan() at startup.
# Replacing the module-level name with a no-op avoids real bot polling.

import endpoints.api as _api_module  # noqa: E402


@asynccontextmanager
async def _noop_telegram():
    yield


_api_module.telegram_lifespan = _noop_telegram  # type: ignore[assignment]

# ── Shared test data ─────────────────────────────────────────────────────────

_NOW = datetime(2026, 6, 13, 12, 0, 0)

_USER = {
    "id": 1,
    "username": "alice",
    "email": "alice@example.com",
    "created_at": _NOW,
}

_KIT = {
    "id": 1,
    "title": "Home kit",
    "created_at": _NOW,
}

_KIT_MEDICINE = {
    "id": 1,
    "first_aid_kit_id": 1,
    "name": "Aspirin",
    "number_of_drugs": 10,
    "expiration_date": date(2027, 12, 31),
    "description": "Pain relief",
}

# Small valid PNG generated via cv2 — used to test non-barcode images.
def _make_blank_png() -> bytes:
    import cv2
    import numpy as np

    img = np.ones((32, 32, 3), dtype=np.uint8) * 255
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


_BLANK_PNG = _make_blank_png()

# ── Client fixture ───────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from endpoints.api import app

    with TestClient(app) as c:
        yield c


# ── GET /  GET /health ───────────────────────────────────────────────────────


class TestMeta:
    def test_root_shape(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert {"service", "docs", "health"} <= r.json().keys()

    def test_health_ok(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


# ── POST /scan ───────────────────────────────────────────────────────────────


class TestScan:
    _SCAN_RESULT = {
        "barcodes": [
            {
                "data": "3856013237097",
                "symbology": "EAN13",
                "rect": {"x": 10, "y": 10, "width": 100, "height": 50},
                "medicine": None,
                "lookup_source": "medum",
                "medum": None,
                "medum_url": "https://medum.ru/3856013237097",
            }
        ]
    }

    def _post(self, client, data: bytes, name="photo.jpg", ct="image/jpeg"):
        return client.post("/scan", files={"file": (name, BytesIO(data), ct)})

    def test_returns_barcodes_list(self, client):
        with patch("endpoints.api.scan_image_bytes", return_value=self._SCAN_RESULT):
            r = self._post(client, b"fake-jpeg")
        assert r.status_code == 200
        barcodes = r.json()["barcodes"]
        assert len(barcodes) == 1
        bc = barcodes[0]
        assert bc["data"] == "3856013237097"
        assert bc["symbology"] == "EAN13"
        assert "rect" in bc

    def test_blank_image_returns_empty(self, client):
        # Real PNG with no barcode — scan_image_bytes runs for real here.
        r = self._post(client, _BLANK_PNG, name="blank.png", ct="image/png")
        assert r.status_code == 200
        assert r.json()["barcodes"] == []

    def test_empty_file_is_400(self, client):
        r = self._post(client, b"")
        assert r.status_code == 400

    def test_non_image_bytes_are_400(self, client):
        r = self._post(client, b"this is not an image")
        assert r.status_code == 400

    def test_missing_file_field_is_422(self, client):
        r = client.post("/scan")
        assert r.status_code == 422


# ── Users CRUD ───────────────────────────────────────────────────────────────


class TestUsers:
    def test_create_201(self, client):
        with patch("endpoints.api.users_service.create_user", return_value=_USER):
            r = client.post("/users", json={"username": "alice", "email": "alice@example.com"})
        assert r.status_code == 201
        body = r.json()
        assert body["id"] == 1
        assert body["username"] == "alice"
        assert body["email"] == "alice@example.com"
        assert "created_at" in body

    def test_create_duplicate_409(self, client):
        with patch("endpoints.api.users_service.create_user", side_effect=IntegrityError()):
            r = client.post("/users", json={"username": "alice", "email": "alice@example.com"})
        assert r.status_code == 409

    def test_create_missing_email_422(self, client):
        r = client.post("/users", json={"username": "alice"})
        assert r.status_code == 422

    def test_create_missing_username_422(self, client):
        r = client.post("/users", json={"email": "alice@example.com"})
        assert r.status_code == 422

    def test_list_200(self, client):
        with patch("endpoints.api.users_service.list_users", return_value=[_USER]):
            r = client.get("/users")
        assert r.status_code == 200
        assert len(r.json()) == 1

    def test_list_limit_zero_400(self, client):
        r = client.get("/users?limit=0")
        assert r.status_code == 400

    def test_list_negative_offset_400(self, client):
        r = client.get("/users?offset=-1")
        assert r.status_code == 400

    def test_get_found_200(self, client):
        with patch("endpoints.api.users_service.get_user_by_id", return_value=_USER):
            r = client.get("/users/1")
        assert r.status_code == 200
        assert r.json()["id"] == 1

    def test_get_not_found_404(self, client):
        with patch("endpoints.api.users_service.get_user_by_id", return_value=None):
            r = client.get("/users/999")
        assert r.status_code == 404

    def test_update_username_200(self, client):
        updated = {**_USER, "username": "alice2"}
        with patch("endpoints.api.users_service.update_user", return_value=updated):
            r = client.patch("/users/1", json={"username": "alice2"})
        assert r.status_code == 200
        assert r.json()["username"] == "alice2"

    def test_update_no_fields_400(self, client):
        with patch(
            "endpoints.api.users_service.update_user",
            side_effect=ValueError("At least one field must be provided for update."),
        ):
            r = client.patch("/users/1", json={})
        assert r.status_code == 400

    def test_update_not_found_404(self, client):
        with patch("endpoints.api.users_service.update_user", return_value=None):
            r = client.patch("/users/1", json={"username": "x"})
        assert r.status_code == 404

    def test_update_conflict_409(self, client):
        with patch("endpoints.api.users_service.update_user", side_effect=IntegrityError()):
            r = client.patch("/users/1", json={"username": "taken"})
        assert r.status_code == 409

    def test_delete_200(self, client):
        with patch("endpoints.api.users_service.delete_user", return_value=True):
            r = client.delete("/users/1")
        assert r.status_code == 200
        assert r.json() == {"deleted": True}

    def test_delete_not_found_404(self, client):
        with patch("endpoints.api.users_service.delete_user", return_value=False):
            r = client.delete("/users/999")
        assert r.status_code == 404


# ── GET /medicines ───────────────────────────────────────────────────────────


class TestMedicines:
    _MED = {"id": 1, "ean13_code": "4605964013002", "medicine_name": "Нурофен"}

    def test_list_200(self, client):
        with patch("endpoints.api.medicines_service.list_medicines", return_value=[self._MED]):
            r = client.get("/medicines")
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body, list)
        assert body[0]["ean13_code"] == "4605964013002"

    def test_list_limit_zero_400(self, client):
        r = client.get("/medicines?limit=0")
        assert r.status_code == 400

    def test_list_negative_offset_400(self, client):
        r = client.get("/medicines?offset=-1")
        assert r.status_code == 400


# ── First-aid kits ───────────────────────────────────────────────────────────


class TestFirstAidKits:
    def test_create_201(self, client):
        with (
            patch("endpoints.api.first_aid_kits_service.users_exist", return_value=True),
            patch("endpoints.api.first_aid_kits_service.create_first_aid_kit", return_value=_KIT),
        ):
            r = client.post("/first-aid-kits", json={"title": "Home kit"})
        assert r.status_code == 201
        body = r.json()
        assert body["id"] == 1
        assert body["title"] == "Home kit"
        assert "created_at" in body

    def test_create_with_user_ids_201(self, client):
        with (
            patch("endpoints.api.first_aid_kits_service.users_exist", return_value=True),
            patch("endpoints.api.first_aid_kits_service.create_first_aid_kit", return_value=_KIT),
        ):
            r = client.post("/first-aid-kits", json={"title": "Shared kit", "user_ids": [1, 2]})
        assert r.status_code == 201

    def test_create_blank_title_400(self, client):
        r = client.post("/first-aid-kits", json={"title": "   "})
        assert r.status_code == 400

    def test_create_unknown_users_404(self, client):
        with patch("endpoints.api.first_aid_kits_service.users_exist", return_value=False):
            r = client.post("/first-aid-kits", json={"title": "Kit", "user_ids": [999]})
        assert r.status_code == 404

    def test_add_medicine_201(self, client):
        with (
            patch(
                "endpoints.api.first_aid_kits_service.get_first_aid_kit_by_id",
                return_value=_KIT,
            ),
            patch(
                "endpoints.api.first_aid_kits_service.add_medicine_to_first_aid_kit",
                return_value=_KIT_MEDICINE,
            ),
        ):
            r = client.post(
                "/first-aid-kits/1/medicines",
                json={
                    "name": "Aspirin",
                    "number_of_drugs": 10,
                    "expiration_date": "2027-12-31",
                    "description": "Pain relief",
                },
            )
        assert r.status_code == 201
        body = r.json()
        assert body["name"] == "Aspirin"
        assert body["number_of_drugs"] == 10
        assert body["expiration_date"] == "2027-12-31"
        assert body["first_aid_kit_id"] == 1

    def test_add_medicine_kit_not_found_404(self, client):
        with patch(
            "endpoints.api.first_aid_kits_service.get_first_aid_kit_by_id",
            return_value=None,
        ):
            r = client.post(
                "/first-aid-kits/999/medicines",
                json={
                    "name": "Aspirin",
                    "number_of_drugs": 5,
                    "expiration_date": "2027-12-31",
                    "description": "Pain relief",
                },
            )
        assert r.status_code == 404

    def test_add_medicine_empty_name_400(self, client):
        with patch(
            "endpoints.api.first_aid_kits_service.get_first_aid_kit_by_id",
            return_value=_KIT,
        ):
            r = client.post(
                "/first-aid-kits/1/medicines",
                json={
                    "name": "",
                    "number_of_drugs": 5,
                    "expiration_date": "2027-12-31",
                    "description": "Pain relief",
                },
            )
        assert r.status_code == 400

    def test_add_medicine_negative_count_400(self, client):
        with patch(
            "endpoints.api.first_aid_kits_service.get_first_aid_kit_by_id",
            return_value=_KIT,
        ):
            r = client.post(
                "/first-aid-kits/1/medicines",
                json={
                    "name": "Aspirin",
                    "number_of_drugs": -1,
                    "expiration_date": "2027-12-31",
                    "description": "Pain relief",
                },
            )
        assert r.status_code == 400

    def test_add_medicine_blank_description_400(self, client):
        with patch(
            "endpoints.api.first_aid_kits_service.get_first_aid_kit_by_id",
            return_value=_KIT,
        ):
            r = client.post(
                "/first-aid-kits/1/medicines",
                json={
                    "name": "Aspirin",
                    "number_of_drugs": 5,
                    "expiration_date": "2027-12-31",
                    "description": "   ",
                },
            )
        assert r.status_code == 400
