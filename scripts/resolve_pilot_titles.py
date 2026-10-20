#!/usr/bin/env python3
"""Resolve frozen pilot slots only after every required annual frame passes audit."""

from __future__ import annotations

import argparse

from film_values.rankings import (
    read_ranking_csv,
    resolve_pilot_titles,
    write_resolved_titles_csv,
)
from film_values.sampling import read_slots_csv


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("slot_csv")
    parser.add_argument("output_csv")
    parser.add_argument("ranking_csv", nargs="+")
    args = parser.parse_args()

    rows = []
    for path in args.ranking_csv:
        rows.extend(read_ranking_csv(path))
    slots = read_slots_csv(args.slot_csv)
    resolved = resolve_pilot_titles(rows, slots)
    write_resolved_titles_csv(args.output_csv, resolved)


if __name__ == "__main__":
    main()
