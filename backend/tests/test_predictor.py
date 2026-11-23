"""Tests for the duration predictor.

The synthetic data has a learnable signal (duration = procedure base x surgeon
speed) while the surgeon's estimate ignores surgeon speed and is optimistic, so
a working model must beat the estimate.
"""

import random
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditEvent, Case, CaseStatus, Hospital, Procedure, Room, Surgeon
from app.services.prediction_service import prediction_accuracy, train_and_apply
from app.services.predictor import DurationPredictor, train_predictor

SPEED = {0: 0.90, 1: 1.0, 2: 1.25}
PROCS = [("P1", 60), ("P2", 90), ("P3", 120)]


def _seed(session: Session, n: int = 360) -> None:
    rng = random.Random(0)
    hospital = Hospital(name="Demo General")
    room = Room(hospital=hospital, code="OR-1")
    surgeons = [
        Surgeon(hospital=hospital, code=f"SUR-{i}", specialty="ortho") for i in range(3)
    ]
    procedures = [
        Procedure(
            hospital=hospital,
            code=code,
            name=code,
            specialty="ortho",
            baseline_duration_minutes=base,
        )
        for code, base in PROCS
    ]
    base_day = date(2025, 1, 6)

    cases = []
    for i in range(n):
        s_idx = rng.randrange(3)
        p_idx = rng.randrange(3)
        procedure = procedures[p_idx]
        base = procedure.baseline_duration_minutes
        actual_minutes = max(10.0, base * SPEED[s_idx] * rng.gauss(1.0, 0.08))
        day = base_day + timedelta(days=i // 6)
        start = datetime(day.year, day.month, day.day, 8, tzinfo=UTC) + timedelta(
            minutes=60 * (i % 6)
        )
        estimate = round(base * 0.85)  # optimistic, ignores surgeon speed
        cases.append(
            Case(
                hospital=hospital,
                patient_ref=f"P-{i:05d}",
                procedure=procedure,
                surgeon=surgeons[s_idx],
                room=room,
                service_date=day,
                scheduled_start=start,
                scheduled_end=start + timedelta(minutes=estimate),
                actual_start=start,
                actual_end=start + timedelta(minutes=actual_minutes),
                surgeon_estimate_minutes=estimate,
                status=CaseStatus.COMPLETED,
            )
        )
    session.add(hospital)
    session.add_all(cases)
    session.commit()


def test_model_beats_surgeon_estimate(session: Session) -> None:
    _seed(session)
    cases = list(session.scalars(select(Case)).all())
    _, result = train_predictor(cases)

    assert result.n_train > 0 and result.n_test > 0
    assert result.model_mae < result.surgeon_mae
    assert result.improvement_pct > 0
    assert 40.0 <= result.within_range_pct <= 100.0


def test_predict_quantiles_are_ordered(session: Session) -> None:
    _seed(session)
    cases = list(session.scalars(select(Case)).all())
    predictor = DurationPredictor.fit(cases)
    lower, median, upper = predictor.predict(cases[:20])
    assert (lower <= median).all()
    assert (median <= upper).all()


def test_train_and_apply_writes_predictions_audit_and_model(
    session: Session, tmp_path: Path
) -> None:
    _seed(session)
    model_path = tmp_path / "duration.joblib"
    result = train_and_apply(session, actor="coordinator", model_path=str(model_path))

    assert result.model_mae < result.surgeon_mae
    assert model_path.exists()

    cases = list(session.scalars(select(Case)).all())
    assert all(c.predicted_duration_minutes is not None for c in cases)

    events = session.scalars(select(AuditEvent)).all()
    assert any(e.action == "predictions.train" for e in events)


def test_saved_model_roundtrips(session: Session, tmp_path: Path) -> None:
    _seed(session)
    cases = list(session.scalars(select(Case)).all())
    predictor = DurationPredictor.fit(cases)
    path = tmp_path / "m.joblib"
    predictor.save(str(path))

    reloaded = DurationPredictor.load(str(path))
    _, median_a, _ = predictor.predict(cases[:10])
    _, median_b, _ = reloaded.predict(cases[:10])
    assert (median_a == median_b).all()


def test_accuracy_after_training(session: Session) -> None:
    _seed(session)
    train_and_apply(session, actor="c", model_path=None)
    accuracy = prediction_accuracy(session)

    assert accuracy.cases_scored > 0
    assert accuracy.model_mae < accuracy.surgeon_mae
    assert accuracy.per_procedure


def test_train_endpoint_requires_role(client: TestClient) -> None:
    assert client.post("/predictions/train").status_code == 422


def test_train_and_accuracy_endpoints(client: TestClient, session: Session) -> None:
    _seed(session)
    trained = client.post("/predictions/train", headers={"X-Role": "coordinator"})
    assert trained.status_code == 200
    body = trained.json()
    assert body["model_mae"] < body["surgeon_mae"]
    assert len(body["examples"]) > 0

    acc = client.get("/predictions/accuracy", headers={"X-Role": "nurse"})
    assert acc.status_code == 200
    assert acc.json()["cases_scored"] > 0
