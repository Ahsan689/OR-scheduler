# ORFlow Simulation (`orsim`)

Synthetic data generator for ORFlow. Produces a reproducible year of
orthopedic operating-room activity as CSV files that the backend import step
consumes. **All data is synthetic**; patients appear only as pseudonymous
references (`P-00001`).

## What it models

- 12 months of weekday cases across 4 ORs
- Orthopedic procedures with **log-normal** duration distributions
- Surgeon-specific **speed** and **optimistic estimate bias** (estimates run
  shorter than reality)
- Turnover variation, late first-case starts, same-day cancellations, no-shows
- Unplanned **emergency** add-on cases (drive overtime)
- Surgeon **block time**, including released and unused blocks
- A fixed seed, so every run is identical

## Usage

```bash
cd simulation
python -m venv .venv && .venv/Scripts/activate   # Windows
pip install -e ".[dev]"

# Generate CSVs into simulation/output/ (gitignored)
python -m orsim --seed 42 --out ./output
```

Programmatic:

```python
from orsim import SimConfig, generate_dataset, write_dataset
from pathlib import Path

dataset = generate_dataset(SimConfig(seed=42))
write_dataset(dataset, Path("output"))
```

## Output files

| File | Columns |
|---|---|
| `hospitals.csv` | name |
| `rooms.csv` | code, name |
| `surgeons.csv` | code, specialty |
| `staff.csv` | code, role |
| `procedures.csv` | code, name, specialty, baseline_duration_minutes |
| `cases.csv` | patient_ref, procedure_code, surgeon_code, room_code, service_date, scheduled_start, scheduled_end, actual_start, actual_end, surgeon_estimate_minutes, status |
| `block_times.csv` | room_code, surgeon_code, service, service_date, start_time, end_time, status |

Status strings mirror the backend enum values so the import step can map them
to real enums.

## Checks

```bash
ruff check . && mypy . && pytest
```
