#!/usr/bin/env python3
"""Freeze year/rank pilot slots before retrieving film titles."""

from __future__ import annotations

import argparse

from film_values.sampling import draw_pilot_slots, write_slots_csv


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output_csv")
    parser.add_argument("--seed", required=True)
    parser.add_argument("--backups-per-period", type=int, default=1)
    args = parser.parse_args()

    slots = draw_pilot_slots(
        seed=args.seed,
        backups_per_period=args.backups_per_period,
    )
    write_slots_csv(args.output_csv, slots)


if __name__ == "__main__":
    main()
