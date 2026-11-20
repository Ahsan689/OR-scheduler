# ORFlow: Operating Room Scheduling & Utilization

A web app that helps hospitals use their operating rooms better: predict how long surgeries take, build smarter daily schedules, and measure the gains against a manual-style baseline.

> **Portfolio project.** All data is **synthetic**. This is not a clinical or production system and must not be used with real patient data.

---

## Why This Project

Operating rooms are a hospital's biggest revenue engine, yet many are still scheduled with phone calls, spreadsheets, and whiteboards. Common costs:

- Idle gaps between cases
- Inaccurate duration estimates, causing overruns and early finishes
- Same-day cancellations
- Unused surgeon block time
- Staff overtime

ORFlow shows how data, prediction, and optimization can reduce these, and how to prove it with numbers.

## Headline Result

*(To be filled in after the simulation step.)*

| Metric | Baseline | ORFlow | Change |
|---|---|---|---|
| Idle minutes per room per day | – | – | – |
| Overtime minutes per day | – | – | – |
| On-time first-case starts | – | – | – |
| Cases per room per day | – | – | – |

Full method and charts: `docs/results.md`.

## Features

- **Synthetic data generator:** 12 months of realistic orthopedic cases across several ORs (reproducible with a fixed seed)
- **Data import:** CSV/Excel upload with validation
- **Utilization dashboard:** idle time, turnover time, overruns, cases per room, on-time starts
- **Duration predictor:** predicts case length with a confidence range and compares it to the surgeon's own estimate
- **Schedule optimizer:** builds daily schedules with OR-Tools, respecting rooms, surgeons, staff, and turnover time
- **Proposal flow:** the optimizer *proposes*, a coordinator *approves or edits*
- **Audit log:** every schedule change is recorded (who, what, before/after, when)
- **Simulation:** replays the same cases under baseline and optimized scheduling and compares results

## Tech Stack

| Layer | Choice |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2 |
| Database | PostgreSQL |
| Prediction | scikit-learn, LightGBM |
| Optimization | Google OR-Tools (CP-SAT) |
| Frontend | Next.js (App Router), TypeScript, Tailwind CSS, Recharts |
| Tooling | Docker Compose, pytest, ruff, mypy, ESLint, GitHub Actions |

## Architecture

```
 Synthetic data / CSV upload
            |
            v
   Ingestion + validation
            |
            v
 PostgreSQL <----> FastAPI backend <----> Next.js frontend
            |
   +--------+---------+
   |                  |
 Duration          Scheduler
 predictor        (OR-Tools)
   |                  |
   +--------+---------+
            |
   Proposals + audit log
            |
            v
   Simulation: baseline vs optimized
```

## Project Structure

```
orflow/
├── README.md
├── CLAUDE.md               # rules for the AI coding agent
├── docker-compose.yml
├── backend/
│   ├── app/
│   │   ├── api/            # routes (thin)
│   │   ├── models/         # SQLAlchemy models
│   │   ├── services/       # business logic: ingestion, predictor, scheduler
│   │   └── core/           # config, auth, audit logging
│   └── tests/
├── frontend/
│   ├── app/
│   └── components/
├── simulation/             # synthetic data + baseline vs optimized comparison
├── notebooks/              # exploration only
└── docs/                   # architecture, results, screenshots
```

## Core Data Model

- **Hospital, Room, Surgeon, Staff**
- **Procedure** (name, code, specialty)
- **Case** (pseudonymous patient ID, procedure, surgeon, room, scheduled and actual times, status)
- **BlockTime** (surgeon or service, room, day, used or released)
- **Proposal** (suggested schedule change, status: pending / accepted / rejected)
- **AuditEvent** (actor, action, before/after, timestamp, source)

Patients are referenced only by pseudonymous IDs such as `P-00123`.

## Build Roadmap

| Step | Deliverable |
|---|---|
| 1 | Project skeleton: Docker, FastAPI health check, Next.js shell, CI |
| 2 | Database models and migrations |
| 3 | Synthetic data generator |
| 4 | CSV/Excel import with validation |
| 5 | Utilization dashboard |
| 6 | Duration predictor vs surgeon estimates |
| 7 | OR-Tools scheduler with proposals and audit log |
| 8 | Simulation: baseline vs optimized, results in `docs/results.md` |
| 9 | Polish: screenshots, live demo, short video, final README |

Target: 4 to 6 weeks.

## Getting Started

```bash
# 1. Clone
git clone <your-repo-url> orflow && cd orflow

# 2. Start the database
docker compose up -d db

# 3. Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload

# 4. Frontend (new terminal)
cd frontend
npm install
npm run dev
```

Run checks:

```bash
cd backend && pytest && ruff check . && mypy .
cd frontend && npm run lint
```

## Design Principles

- **Human in the loop:** the system proposes; a person approves.
- **Auditability:** every change is traceable.
- **Privacy by design:** synthetic data only, pseudonymous IDs, no secrets in the repo.
- **Configurable rules:** weights, turnover times, and constraints live in settings, not hardcoded.
- **Reproducibility:** fixed seeds so results can be re-run and verified.

## Limitations

- Data is simulated, so real-world accuracy is unproven.
- No integration with hospital systems (EHR).
- Single hospital, single specialty.
- Not validated by clinicians.
- Not a medical device and not intended for production use.

## Future Work

**Toward real-world use**
- Retrain the predictor on real, anonymized hospital data
- Hospital system integration (exports first, then FHIR/HL7)
- Security and compliance work (HIPAA or local equivalent, encryption, access reviews)
- Monitoring, backups, and a manual fallback plan
- Multi-hospital support
- Clinical review of scheduling rules with OR managers

**AI agent phase (not started)**
- Pre-surgery readiness checks (consent, labs, fasting, equipment)
- Reading clinical notes to find missing information
- Automated reminders to staff and patients
- Cancellation-risk prediction and waitlist filling

## License

To be decided.
