# Pilot box-office frames (1982–2024 selected years)

This directory contains metadata-only ranking work for the 12 modern-regime years selected by the frozen pilot draw. No reviews, criticism, synopses, or other thematic sources were opened.

## Files

- `pilot_rankings_1982_2024.csv`: 420 cohort rows—35 for each selected or backup year—using the schema frozen in `docs/BOX_OFFICE_SAMPLING.md`.
- `pilot_title_resolution_1982_2024.csv`: the selected rank in each of the 12 frozen year slots and its resolved title.
- `excluded_rereleases_1982_2024.csv`: source rows omitted while constructing cohort rank 1–35.
- `source_access_log.csv`: one primary and one audit access record per year, plus the three primary title-metadata checks used for exclusions.

## Ranking rules applied

Box Office Mojo's release-year `?grossesOption=totalGrosses` view is primary. Explicitly labeled rereleases were removed before assigning `cohort_rank`, but their removal did not compress `source_row_order`. Content eligibility was applied only afterward; content-ineligible original releases remain in `cohort_rank`.

For compatibility with the ranking validator, these rows use `source_regime=bom_total_gross`, `metric=domestic_gross`, `source_amount_type=release_run_total`, and `release_date_precision=day`.

The excluded rerelease rows that affected the first 35 cohort positions were:

- 1982: *Bambi 1982 Re-release* (source row 32) and *Raiders of the Lost Ark 1982 Re-release* (source row 34).
- 1983: *Snow White and the Seven Dwarfs 1983 Re-release* (source row 23) and *The Rescuers 1983 Re-release* (source row 36).
- 1988: *Bambi 1988 Re-release* (source row 28).
- 2011: *The Lion King 2011 3D Release* (source row 33).

Three original-release cohort rows were retained but marked analytically ineligible using Box Office Mojo title-page format/genre metadata: *Richard Pryor: Live on the Sunset Strip* (filmed concert/performance), *Everest* (documentary), and *March of the Penguins* (documentary). This does not alter `cohort_rank`. All 12 initially selected ranks resolve to eligible narrative features; no rank replacement was used.

The Numbers released-in-year cumulative chart is an audit only. Its values can include later rerelease earnings, so rank and amount differences are flags rather than corrections to the primary. Alternate/translated-title matches are recorded in `adjudication_note`; all 420 primary rows obtained one unique audit match.

## Reproducibility and limitations

Retrieval times are UTC. `amount` and `secondary_amount` are nominal U.S. dollars. `source_amount_type` is `release_run_total` as required for this regime. `near_tie_flag` is true for either member of an adjacent primary-source pair differing by less than 1%; exact ties are separately flagged.

No raw HTML snapshot was retained in the repository, so `artifact_path` and `artifact_sha256` are intentionally blank. The exact query URLs, retrieval times, status codes, and response sizes are preserved. Both sources returned HTTP 200 for every recorded retrieval. An initial anonymous-style The Numbers request returned HTTP 403, but a subsequent identified research-metadata user agent succeeded for all 12 pages; therefore there is no unresolved data-access blocker for these frames.
