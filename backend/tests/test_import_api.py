"""Tests for the /import endpoint, including the role gate."""

from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Hospital

HOSPITAL_CSV = b"name\nDemo General Hospital\n"


def _post(client: TestClient, **kwargs: object) -> Response:
    return client.post(
        "/import",
        data={"kind": "hospitals"},
        files={"file": ("hospitals.csv", HOSPITAL_CSV, "text/csv")},
        **kwargs,  # type: ignore[arg-type]
    )


def test_missing_role_header_is_rejected(client: TestClient) -> None:
    response = _post(client)
    assert response.status_code == 422  # required X-Role header missing


def test_unknown_role_is_unauthorized(client: TestClient) -> None:
    response = _post(client, headers={"X-Role": "wizard"})
    assert response.status_code == 401


def test_nurse_is_forbidden(client: TestClient) -> None:
    response = _post(client, headers={"X-Role": "nurse"})
    assert response.status_code == 403


def test_coordinator_can_import(client: TestClient, session: Session) -> None:
    response = _post(client, headers={"X-Role": "coordinator", "X-Actor": "alice"})
    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "hospitals"
    assert body["created"] == 1

    hospital = session.scalars(select(Hospital)).one()
    assert hospital.name == "Demo General Hospital"


def test_unsupported_file_type_is_bad_request(client: TestClient) -> None:
    response = client.post(
        "/import",
        data={"kind": "hospitals"},
        files={"file": ("hospitals.txt", HOSPITAL_CSV, "text/plain")},
        headers={"X-Role": "admin"},
    )
    assert response.status_code == 400
