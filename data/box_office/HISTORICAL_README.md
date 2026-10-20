# Provisional historical pilot-frame work

These files document ranking-only work for the pre-1982 pilot slots. No reviews, synopses, criticism, or thematic evidence were used. Full *Variety* scans remain outside Git; the repository stores citations, locators, retrieval times, and hashes only.

Protocol v0.4 ranks the six originally drawn historical cohorts on each title's latest cumulative U.S.-Canada distributor rentals available by the common cutoff. The mechanically selected 1952 `backup_2` is a frozen cohort-specific exception: it uses the latest like-for-like projected-ultimate U.S.-Canada distributor rental available through January 31, 1954. It is explicitly a pilot rule, not a claim that either amount type exists throughout 1950–1981.

The public seed is the full identifier of the repository's initial prospective-protocol commit, `44dfaae218b8f9f195f633840f16099f047d4398`. The 1952 backup is the fourth year in the already-frozen 1950–1962 seed ordering after the originally assigned development, validation, and backup slots; its rank order is generated from the same seed without consulting film identities or themes. Cross-table exact ties are ordered by ascending `SHA256(public_seed|cohort_year|stable_title_id)` only after cohort membership is resolved.

Files:

- `historical_frame_status.csv` is the authoritative progress/blocker table, including the mechanically generated 1952 `backup_2` slot.
- `historical_source_access_log.csv` records issue URLs, page locators, UTC access times, and hashes of temporary source artifacts.
- `historical_method_notes.csv` records the source-native amount labels and the verified distinction between current and projected amounts.
- `historical_adjudication_log.csv` preserves cross-year, missing-amount, method-change, and deterministic tie evidence.
- `historical_1952_projection_audit.csv` records both annual-table amounts, release-cohort checks, rank ranges, omissions, and the machine-readable provisional rank-12 result for the replacement backup.
- `pilot_rankings_1959_provisional.csv` is the first complete provisional historical frame. It includes rank 36 because the exact $2.0m tie crosses the nominal rank-35 capture boundary.

The 1960 frame is blocked because *Spartacus* has no located cumulative domestic rental within the cutoff. A title-specific search found a contemporaneous $17m worldwide theater-gross report, which is the wrong metric, and a $14m U.S.-Canada rental in January 1963, which is outside the frozen cutoff. The independent 1960 top-ten reconstruction also prompted a cohort check for *The World of Suzie Wong*: AFI records a November 1960 New York premiere, and the title does have a January 1962 cumulative row.

The mechanically generated 1952 backup failed the pilot-wide cumulative rule, and that failure remains in the adjudication history. The dated v0.4 amendment now gives this cohort a `projected_ultimate` rule. Both the January 1953 and January 1954 page images have been checked, including the deferred late-1952 titles and the complete plausible top-35 omission set. The unique provisional rank-12 title is *With a Song in My Heart* at $3.25 million. Every candidate capable of reaching the top-35 boundary has a comparable projection.

The full 1952 top-35 frame is not yet frozen. AFI records a 31 December 1952 Washington world premiere for *Above and Beyond* and a 2 January 1953 release date, but the premiere still needs confirmation as revenue-generating public commercial play under the protocol's cohort definition. If included, the $2.5 million title places *Because You're Mine* at rank 35; if excluded, *Because You're Mine* moves to rank 34 and the $2.4 million tie below it crosses the capture boundary. Cross-table exact-tie hashes will be applied only after this cohort question is resolved.

Every title and rank remains provisional until all historical frames and release-date assignments pass the repository's final validator. `eligibility=unresolved` in the 1959 file is deliberate: content eligibility was not assessed during ranking reconstruction.
