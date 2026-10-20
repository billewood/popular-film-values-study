# Frozen Pilot Draw Procedure

**Established:** 2026-10-19

The pilot uses two-stage, metadata-only selection so that titles cannot be chosen according to their known themes or the availability of favorable interpretations.

## Public seed

The seed is the full identifier of the repository's initial prospective-protocol commit:

```text
44dfaae218b8f9f195f633840f16099f047d4398
```

This commit was already pushed publicly before the pilot draw procedure was executed.

## Algorithm

For each of the six historical periods, the deterministic algorithm:

1. orders every year in the period by a SHA-256 digest of the public seed, period, and year;
2. assigns the first distinct year to development, the second to validation, and the third to a presampled backup;
3. orders ranks 11–25 separately for each slot by a SHA-256 digest of the seed, period, assignment, year, and rank; and
4. selects the first rank while retaining the complete rank order as the within-year replacement sequence.

The algorithm is implemented in `src/film_values/sampling.py` and tested in `tests/test_sampling.py`.

## Replacement rules

- If the film at the selected rank is not an eligible narrative feature under the frozen protocol, use the next rank in that slot's recorded replacement order.
- Do not replace a title because of its themes, likely conclusions, critical reputation, source viewpoint, or ease of interpretation.
- If an otherwise eligible film fails the minimum source-coverage rule, record that failure and move to the period's presampled backup slot.
- Any circumstance not covered above requires a dated amendment before a replacement is made.

The generated slot table is committed as `data/pilot_slots.csv`. It contains no thematic data or film titles.
