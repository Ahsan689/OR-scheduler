# CLAUDE.md

Instructions for Claude Code when working on **ORFlow**, an operating room (OR) scheduling and utilization app. Read `README.md` first for project context.

## Project Purpose

This is a **portfolio project**. The goal is a polished, finished, demo-able app built on **realistic synthetic data**, with a measurable before/after result (for example: "optimized schedule cuts idle OR time by X% versus a naive schedule on simulated data").

Priorities, in order:
1. Working, clean, tested code
2. A clear demo (live link, screenshots, short video)
3. A strong README with architecture, results, and honest limitations
4. Finishing within about 4 to 6 weeks. A finished small project beats an unfinished big one.

## Current Phase

Build the **core app only**: synthetic data, import, utilization dashboard, duration prediction, schedule optimization, and a simulation that compares schedules.

**Do NOT build any LLM or AI-agent features.** No Claude API calls, no `anthropic` package, no prompt files, no note extraction or readiness-checking agent. That is a later phase and will only be added when explicitly requested.

## Tech Stack (do not change without asking)

- Backend: Python 3.12, FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2
- Database: PostgreSQL
- Prediction: scikit-learn / LightGBM
- Scheduling: Google OR-Tools (CP-SAT)
- Frontend: Next.js (App Router), TypeScript, Tailwind CSS, a charting library (Recharts)
- Tooling: Docker Compose, pytest, ruff, mypy, ESLint, GitHub Actions
- Redis and Celery: add only if a background job genuinely needs them. Do not add by default.

## Project Structure

Follow the folder layout in `README.md`. Put new code in the matching folder. Do not create new top-level directories without asking.

```
backend/app/{api,models,services,core}
backend/tests/
frontend/{app,components}
simulation/      # synthetic data + schedule comparison
notebooks/       # exploration only
docs/            # architecture, results, screenshots
```

## How to Work

1. **One small task at a time.** Do exactly what is asked. No extra features, no unrelated refactors.
2. **Plan before coding** for anything non-trivial: list the files you will touch and your approach, then wait for a go-ahead if the change is large.
3. **Tests first** for the scheduler, duration predictor, data import/validation, and the simulation metrics.
4. **Before saying a task is done**, run tests, `ruff`, and `mypy` (backend) and lint (frontend). Report the real results. If something fails or could not be run, say so plainly.
5. **Small commits.** Suggest a clear commit message after each working step. Never force-push or rewrite history.
6. **Ask when unsure** about data models or scheduling rules instead of guessing.
7. **Stop after each build step** and wait for review before starting the next.

## Code Standards

- Type hints on all Python functions. `ruff` and `mypy` must pass clean.
- Business logic lives in `services/`. Route handlers stay thin.
- Validate all input with Pydantic. Never trust uploaded files.
- Every schema change goes through an Alembic migration.
- Config comes from environment variables via `core/config.py`. No hardcoded secrets or URLs.
- Prefer clear, boring code. Comment only where the reason is not obvious.
- Frontend: strict TypeScript, no `any`, small components, loading and error states on every fetch, responsive layout.

## Data and Safety Rules

- **Synthetic data only.** Never add real patient data to the repo, tests, or demo.
- Use pseudonymous IDs (e.g. `P-00123`). No names or personal identifiers anywhere.
- Never log secrets or full request bodies.
- **Every schedule or case change writes an `AuditEvent`:** actor, action, before/after values, timestamp, source.
- **The system proposes; a human approves.** Optimizer output is saved as a *proposal* and applied only after a user accepts it.
- Role-based access (coordinator, surgeon, nurse, admin) on endpoints that return or change case data.
- Never commit `.env`. Keep `.env.example` current.
- The README and demo must state clearly that data is simulated and this is not a clinical or production system.

## Synthetic Data Requirements

Make the data realistic enough to be convincing:
- 12 months of orthopedic cases across 3 to 4 ORs
- Procedure types with different duration distributions (log-normal, not uniform)
- Surgeon-specific speed and a bias in their own estimates (usually optimistic)
- Turnover time variation, late starts, emergencies, and same-day cancellations
- Surgeon block time with some unused blocks
- A fixed random seed so results are reproducible

## Scheduling Rules

- Hard constraints: one case per room at a time, surgeon and staff availability, room/equipment availability, turnover time between cases.
- Soft goals (idle gaps, overtime, unused block time) use configurable weights, not hardcoded numbers.
- The solver is deterministic for a given input and seed, and returns a clear reason when no feasible schedule exists.
- Duration predictions show a confidence range and are compared against the surgeon's own estimate.

## Simulation and Results

Build a simulation that replays the same set of cases under:
- **Baseline:** naive/manual-style scheduling using surgeon estimates
- **Optimized:** predicted durations plus the OR-Tools scheduler

Report: idle minutes per room, overtime minutes, on-time first-case starts, cases per room per day, and same-day cancellation impact. Save the results to `docs/results.md` with charts. These numbers are the headline of the portfolio.

## Commands

```bash
docker compose up -d db                 # start services
cd backend && uvicorn app.main:app --reload
cd backend && pytest                    # tests
cd backend && ruff check . && mypy .    # lint and types
cd frontend && npm run dev              # frontend
cd frontend && npm run lint
```

## Build Order (follow in sequence)

1. Project skeleton: Docker Compose, FastAPI health check, Next.js shell, `.gitignore`, `.env.example`, CI
2. Database models and migrations (hospital, room, surgeon, procedure, case, block time, audit event)
3. Synthetic data generator (in `simulation/`)
4. CSV/Excel import with validation
5. Utilization dashboard (idle minutes, turnover, overruns, cases per room)
6. Duration predictor with baseline comparison against surgeon estimates
7. Scheduler (OR-Tools) with proposals and accept/edit flow, plus audit log
8. Simulation: baseline vs optimized, results written to `docs/results.md`
9. Polish: README with architecture diagram and results, screenshots, deploy a live demo, short demo video

## Out of Scope

- LLM or AI-agent features (planned for a later phase)
- EHR integration (Epic, Cerner, HL7/FHIR)
- Multi-hospital or multi-tenant support
- Native mobile apps
- Billing, payments, or insurance features
- Real patient data of any kind
