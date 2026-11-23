"""Command-line entrypoint: ``python -m orsim``.

Generates the default dataset and writes CSVs to an output directory.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

from orsim.config import SimConfig
from orsim.generator import generate_dataset
from orsim.writer import write_dataset


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate ORFlow synthetic data.")
    parser.add_argument("--seed", type=int, default=SimConfig.seed, help="Random seed.")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "output",
        help="Output directory for CSV files.",
    )
    args = parser.parse_args(argv)

    config = replace(SimConfig(), seed=args.seed)
    dataset = generate_dataset(config)
    paths = write_dataset(dataset, args.out)

    print(f"Wrote {len(dataset.cases)} cases and {len(dataset.block_times)} blocks to {args.out}")
    for name, path in paths.items():
        print(f"  {name:12s} -> {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
