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

## Metadata-frame amendment

On 2026-10-19, reconstruction showed that the 1960 backup frame for the 1950–1962 period is not constructible under the frozen cutoff: no cumulative U.S.–Canada distributor-rental figure for *Spartacus* could be located by January 31, 1962. A later worldwide theater-gross figure is not commensurate, and the first located U.S.–Canada rental is outside the cutoff. The failed slot remains in the table.

Before any interpretive-source search or theme extraction, `backup_2` was added for that period using the fourth year in the original public-seed year ordering. This mechanically selects 1952 and derives its rank order with the unchanged algorithm and seed. The added slot is an insurance frame only; it does not enlarge the scored pilot and may be used only if the original backup is needed. If 1952 is also nonconstructible, the period stops pending another dated amendment rather than substituting an incomparable ranking quantity.
