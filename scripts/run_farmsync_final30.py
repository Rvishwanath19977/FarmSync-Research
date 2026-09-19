#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from farmsync import final30


def main():
    parser = argparse.ArgumentParser(
        description=(
            "FarmSync frozen publication Final30 runner"
        )
    )

    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "Verify frozen matrix/data/provenance only. "
            "Runs no solver and writes no Final30 output."
        ),
    )

    parser.add_argument(
        "--family",
        default="ALL",
        choices=[
            "ALL",
            *final30.FAMILY_ORDER,
        ],
        help="Publication experiment family to execute.",
    )

    parser.add_argument(
        "--seed",
        action="append",
        type=int,
        help=(
            "Execute only this frozen master seed. "
            "May be specified multiple times."
        ),
    )

    args = parser.parse_args()

    if args.check:
        final30.check()
        return 0

    final30.execute(
        family=args.family,
        seeds=args.seed,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
