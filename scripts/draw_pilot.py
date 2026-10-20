#!/usr/bin/env python3
"""Draw the pilot sample from a frozen candidate CSV."""

from __future__ import annotations

import argparse

from film_values.sampling import draw_pilot, read_candidates_csv, write_selections_csv


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate_csv")
    parser.add_argument("output_csv")
    parser.add_argument("--seed", required=True)
    parser.add_argument("--backups-per-period", type=int, default=1)
    args = parser.parse_args()

    candidates = read_candidates_csv(args.candidate_csv)
    selections = draw_pilot(
        candidates,
        seed=args.seed,
        backups_per_period=args.backups_per_period,
    )
    write_selections_csv(args.output_csv, selections)


if __name__ == "__main__":
    main()
