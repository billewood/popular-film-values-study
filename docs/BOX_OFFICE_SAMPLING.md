# Box-office sampling protocol, 1950–2025

## Status and scope

This document freezes the source and adjudication rules for constructing annual U.S./Canada theatrical-popularity frames before film identities are resolved from the already-frozen year/rank slots and before any thematic evidence is collected. It covers (a) the 12-film pilot, sampled from annual cohort ranks 11–25 within the six prespecified periods, and (b) the later census of films occupying cohort ranks 1–10 in each year from 1950 through 2025.

The estimand is **release-year popularity**: the popularity of films whose first commercial domestic theatrical release occurred in year *y*, measured over the release's first run. It is not the set of films that happened to earn money during calendar year *y*. This distinction matters especially for December releases, films with long runs, and rereleases.

## Decision in brief

Use a two-regime hierarchy and never convert or pool the monetary amounts across regimes:

| Release years | Primary ranking evidence | Metric | Construction |
|---|---|---|---|
| 1950–1981 | *Variety* annual “Top Grossers” / “Big Rental Films” tables, checked against the printed page image | U.S.–Canada distributor rentals | Reconstruct a release-year cohort from the annual tables for reporting years *y* and *y*+1; exclude rereleases and retain each eligible title's latest first-run estimate available by the fixed cutoff |
| 1982–2025 | [Box Office Mojo yearly chart](https://www.boxofficemojo.com/year/) with `grossesOption=totalGrosses` for year *y* | Domestic theatrical gross for releases opened in *y*, across the run reported by the database | Download at least raw ranks 1–35, verify that the page is in release-year rather than calendar-gross mode, then apply eligibility rules |

Use [The Numbers release-year cumulative chart](https://www.the-numbers.com/box-office-records/domestic/all-movies/cumulative/released-in-2024) as the routine independent audit for 1982–2025. Use licensed Comscore data or a documented distributor correction only for adjudication if available; do not substitute a public calendar-year list. The 1982 boundary is retained as an explicit `metric_regime` break.

This hierarchy is preferable to a superficially uniform series. Historical rental and modern gross figures are different constructs, but each is the best available contemporaneous measure of theatrical reach within its year. Because the study uses annual ranks rather than dollar comparisons across years, the discontinuity is contained, although not eliminated.

## Operational definitions

### Cohort year

Assign a film to the calendar year of its **first revenue-generating public commercial theatrical engagement in the domestic market**. A festival premiere, press screening, private screening, or foreign opening does not start the domestic cohort. A commercial awards-qualifying engagement does. For a foreign-produced film, use its first domestic commercial release, not its original-country premiere.

For 1950–1974, verify dates in the [AFI Catalog of Feature Films](https://catalog.afi.com/) where the title is covered; AFI is a release-date authority, not a popularity-ranking source. Thereafter use, in order, the primary chart's release field, a distributor release record, and concordant Box Office Mojo/The Numbers title records. Record the source used and whether the date was exact, month-only, or inferred. Unresolved year assignments are not guessed.

### Domestic market

The historical *Variety* tables explicitly define domestic as the United States and Canada. Current Box Office Mojo documentation is internally inconsistent: its [FAQ](https://help.imdb.com/article/imdbpro/industry-research/box-office-mojo-by-imdbpro-faq/GCWTV4MQKGWRAUAP) describes “domestic” as the United States, Canada, and Puerto Rico, while its country table labels the region “US & Canada.” The Numbers also uses a slightly broader North American definition. Therefore, `territory_definition` must be stored verbatim by source and the study must describe the series as source-defined domestic theatrical popularity, principally U.S.–Canada, rather than claiming a perfectly invariant geography.

### Monetary measures

* **Gross** is the money taken in from theater ticket sales. Box Office Mojo's [glossary](https://help.imdb.com/article/imdbpro/industry-research/box-office-by-imdbpro-glossary/GN8HA87MT4597FSW) excludes home entertainment, television rights, and other ancillary revenue.
* **Distributor rental** is the distributor's share of theatrical receipts, after the exhibitor share. It is not video rental revenue and is not total box-office gross.

No universal rental-to-gross multiplier is defensible because film-rental terms varied by picture, distributor, venue, and run. Monetary values are used only to order titles within the same release year and metric regime.

### Eligible work and rerelease

Apply the project's prespecified screen-content eligibility rules after the raw chart is captured. Retain fictional or dramatized narrative feature films, including sequels. Exclude documentaries, concert films, filmed stage performances, episodic/event-cinema packages, and rereleases/restorations/anniversary engagements.

A **rerelease** is a theatrical engagement of substantially the same motion-picture work after an earlier domestic commercial theatrical release. It remains a rerelease even when a database gives the engagement a new row, subtitle, or release date. A materially new feature-length cut should be escalated for adjudication and documented before inclusion.

Keep three distinct fields:

* `source_row_order`: order in the printed or rendered source table;
* `cohort_rank`: order after release-year reconstruction, removal of rerelease rows, and deduplication, but **before** content-type eligibility screening; and
* `eligible_rank`: optional descriptive order after content-type exclusions; it is not the pilot selection rank.

The public draw's `selected_rank` refers to `cohort_rank`. If that row is not an eligible narrative feature, the pilot advances through that slot's frozen rank-replacement order; it does not compress the table first. This is required by the already-frozen [pilot-draw procedure](PILOT_DRAW.md). The future main frame should likewise begin with cohort ranks 1–10 and then apply content eligibility, rather than silently backfilling with rank 11 or below. If the main study instead requires exactly ten eligible narrative films in every year, that is a different estimand and must be adopted in a dated amendment before main-sample titles are resolved. Capture at least the raw top 35 every year so exclusions, deduplication, and sensitivity checks are not truncated.

## Pilot implementation after the public draw

The public seed fixed metadata-only year/rank slots before titles or themes were inspected. The immediately required frames are:

| Period | Development | Validation | Presampled backup |
|---|---:|---:|---:|
| 1950–1962 | 1959, rank 23 | 1962, rank 14 | 1960, rank 13 |
| 1963–1975 | 1968, rank 20 | 1966, rank 21 | 1965, rank 19 |
| 1976–1988 | 1983, rank 16 | 1988, rank 24 | 1982, rank 19 |
| 1989–2001 | 1992, rank 23 | 1998, rank 21 | 1999, rank 13 |
| 2002–2014 | 2009, rank 13 | 2011, rank 18 | 2005, rank 16 |
| 2015–2025 | 2021, rank 17 | 2024, rank 22 | 2018, rank 13 |

For each of these 18 years, construct and freeze the entire cohort through at least rank 35; do not retrieve only the selected row. Resolve development and validation slots in the exact `rank_replacement_order` recorded in [`data/pilot_slots.csv`](../data/pilot_slots.csv). Advance within that order only when a ranked work fails the already-frozen narrative-feature eligibility rule. An otherwise eligible film that fails the separately frozen minimum interpretive-source coverage rule moves the period to its presampled backup-year slot; box-office source inconvenience is not itself a reason to change films. Every skip receives the predefined exclusion/failure code before the next title is opened.

All 18 frames, their source artifacts, and the title-resolution log should be frozen before any selected film's interpretive-source search begins. This prevents availability or thematic knowledge learned in an early search from influencing a later rank or historical transcription.

## Regime A: 1950–1981

### Why *Variety* is primary

The relevant *Variety* Anniversary Edition tables are contemporaneous trade reports of domestic distributor rentals. Their own notes define the market and metric, identify estimates, flag reissues, and explain that late releases may be omitted until the next year's compilation. Examples include:

* “Top-Grosses of 1950,” *Variety*, January 3, 1951, p. 58 ([page-image scan](https://archive.org/details/variety181-1951-01/page/n57/mode/1up));
* “Rental Potentials of 1960,” *Variety*, January 4, 1961, p. 47 ([page-image scan](https://www.worldradiohistory.com/Archive-All-Music/Variety/Variety-55th-1961-01-04.pdf));
* “Big Rental Films of 1971,” *Variety*, January 5, 1972 ([page-image scan](https://www.worldradiohistory.com/Archive-All-Music/Variety/Variety-1972-01-05.pdf));
* “Big Rental Films of 1974,” *Variety*, January 8, 1975, p. 24 ff. ([page-image scan](https://www.worldradiohistory.com/Archive-All-Music/Variety/Variety-69th-1975-01-03.pdf));
* “Big Rental Films of 1975,” *Variety*, January 7, 1976, pp. 18, 52 ([page-image scan](https://www.worldradiohistory.com/Archive-All-Music/Variety/Variety-70th-Anniversary-1976.pdf));
* “Big Rental Films of 1976,” *Variety*, January 5, 1977, pp. 14, 44 ([page-image scan](https://www.worldradiohistory.com/Archive-All-Music/Variety/Variety-71st-1977.pdf)); and
* “Big Rental Films of 1981,” *Variety*, January 13, 1982, pp. 15, 42.

The method is not perfectly uniform even within the historical series. The 1950 chart describes films sent into release in 1950 and projects ultimate U.S.–Canada rentals from results to date; the 1960 chart includes projections and carryovers. By the 1970s, the notes describe calendar-year rental compilations with late prior-year films, deferred current-year films, and reissues. The 1971 and 1976 tables explicitly say that rentals accrue to distributors rather than equal total theater receipts and use a $1 million threshold. They therefore cannot be copied as if they were already uniform release-year rankings. The 1976 list, for example, is headed by *One Flew Over the Cuckoo's Nest*, released in November 1975. Each issue's method note must be transcribed alongside its rows.

### Release-year reconstruction

For each release year *y* from 1950 through 1981:

1. Obtain and archive the *Variety* annual table published just after reporting year *y* and the table published just after *y*+1. Transcribe the issue-specific method note. Consult *y*+2 only if a title is explicitly deferred or its first complete first-run estimate is still absent.
2. Double-enter all potentially relevant rows from the page images, including title, displayed amount, source order, release month/year, distributor, estimated/anticipated notation, and reissue notation. OCR may assist discovery but cannot be the final transcription authority.
3. Verify first domestic commercial release year. Retain only films assigned to *y*.
4. Classify each amount from its table note as projected ultimate, cumulative-to-date, or reporting-year rental. For a title appearing more than once, use the latest comparable first-run estimate available through **January 31 of *y*+2**. Do not add figures unless the source explicitly defines them as incremental components, and do not substitute a reporting-year amount for a projected-ultimate amount without flagging the change. Never incorporate a later rerelease.
5. Exclude explicit rereleases, deduplicate title/run records, and rank descending by the retained amount. Preserve non-narrative and otherwise content-ineligible original releases in `cohort_rank`; apply content eligibility only after that rank is fixed. Where only a printed ordering is available, preserve that ordering and mark the amount unavailable.
6. Preserve the table, issue, page, and exact cell/row provenance for every retained value.

This rule gives late-year releases one additional annual table while imposing the same information horizon on every historical cohort. It also prevents later successful reissues from changing a film's original-release-year popularity.

### Access and transcription hierarchy

Use the best available page image in this order: (1) licensed *Variety* archive/EIMA or an original library scan; (2) Media History Digital Library or Internet Archive scan; (3) WorldRadioHistory page-image scan. A later transcription, including Suzanne Mary Donahue's *American Film Distribution: The Changing Marketplace* (UMI Research Press, 1987; [catalog record](https://books.google.com/books/about/American_Film_Distribution.html?id=QmhZAAAAMAAJ)), may audit a value but does not override a legible primary page.

The [UCLA *Variety* research guide](https://guides.library.ucla.edu/film/varietymag) documents the principal access routes: the weekly magazine in ProQuest's Entertainment Industry Magazine Archive for 1905–2000, free historical scans for only part of the period, and the official complete archive onsite at the Academy's Margaret Herrick Library. Each transcribed table must be checked by a second pass against the image; disagreements are resolved from the image and logged.

## Regime B: 1982–2025

### Box Office Mojo primary extraction

For year *y*, use:

`https://www.boxofficemojo.com/year/YYYY/?grossesOption=totalGrosses`

The `totalGrosses` view groups releases by opening year and ranks them by the reported total gross of that release/run. It is the appropriate view for the project's “films released in each year” question. In contrast, `grossesOption=calendarGrosses` ranks receipts earned during the calendar year and can include prior-year releases.

This distinction must be verified in the saved page, not inferred from a generic “Domestic Box Office for YYYY” heading. The [Box Office Mojo methodology](https://www.boxofficemojo.com/article/ed3547792388/) distinguishes charts by release date from calendar-gross charts and describes documented period data from 1982 onward. Its [FAQ](https://help.imdb.com/article/imdbpro/industry-research/box-office-mojo-by-imdbpro-faq/GCWTV4MQKGWRAUAP) says data arrive from studios, distributors, sales agents, and other industry sources. The 1980–1981 public yearly pages are materially incomplete, so 1982 is the first year accepted for this protocol.

Store both the displayed year-specific `Gross` and `Total Gross` fields when present, but rank on the release-year view's `Total Gross`/source order as rendered. Inspect title-level records where the two differ, because a separate rerelease engagement or database aggregation can otherwise contaminate an original-run total. Exclude database rows explicitly labeled “re-release” and document any manual separation of later engagements.

### Independent audit

For the same year, capture The Numbers page:

`https://www.the-numbers.com/box-office-records/domestic/all-movies/cumulative/released-in-YYYY`

The page states that it ranks films released in that year by total cumulative North American earnings across all years played, as distinct from films that merely earned money during the year. That makes it a useful release-year audit, not an interchangeable primary. Its historical aggregation of reissues and its domestic-territory definition can differ from Box Office Mojo. Its separate calendar-year pages also use a non-calendar “box-office year” convention, so those pages are not used for selection.

Compare the primary and audit source through raw rank 35, normalized by stable title/release identifiers. Log rank, amount, release date, and rerelease/aggregation disagreements. Never average values or splice the two orderings.

[Comscore Movies](https://www.comscore.com/Products/Movies/Global-Box-Office-Reporting) is the upstream industry standard for near-real-time theatrical reporting, but its complete historical/title-level service is proprietary. If licensed access becomes available, use it to investigate a disputed title, not to silently replace already frozen years. Public year-end Comscore releases generally do not supply release-year ranks 11–25 and therefore cannot construct the pilot frame.

## Conflict, tie, and missing-data rules

1. **Diagnose definitions first.** A difference caused by rentals versus gross, reporting year versus release year, source-native territory, cumulative horizon, or rerelease aggregation is a definitional difference, not a transcription error.
2. **Primary source governs selection.** Correct it only for a publisher erratum or a demonstrable transcription/OCR error verified against the page image. Record the correction and evidence.
3. **Boundary conflicts receive heightened review.** Flag any disagreement affecting cohort ranks 10/11 or 25/26, or an already-drawn pilot rank. Retain the primary-source sample, and preregister the alternate-source membership as a sensitivity analysis where feasible.
4. **Exact ties preserve the publisher's order** unless the publisher explicitly declares a tie. If an explicit tie includes a drawn pilot rank, treat all tied rows as one unresolved rank block and apply a public-seed hash tie-break based only on stable title identifier; record the full tied set. If a tie crosses the main-study rank-10 boundary, retain the full tie set and report that the year contains more than 10 co-ranked films.
5. **Near ties are not ties.** Preserve source order but flag adjacent amounts differing by less than 1% as `rank_near_tie`, because rounding or later corrections could reverse them.
6. **Unresolved cases remain unresolved.** Do not invent a release year or amount. For the pilot, advance through that slot's recorded `rank_replacement_order` only after the unresolved status and evidence are logged. For the main study, report the missing/adjudication case and perform a membership sensitivity analysis.

## Reproducible freeze rule

The metadata-only pilot draw has already been executed from a public seed without titles. Complete and freeze all 18 selected and backup-year frames **before** any review, synopsis, or theme material is retrieved. Complete the remaining 1950–2025 frames before resolving the future main-sample titles. The freeze package must contain:

* protocol version and freeze date;
* every raw source row needed to recover ranks through at least 35;
* source URL plus all query parameters, or publication title, issue date, and page number;
* retrieval time in UTC and, where lawful, the saved HTML/PDF/page image;
* SHA-256 hash of each saved artifact;
* source regime, monetary metric, territory definition, displayed amount, source-row order, cohort rank, and estimate flag;
* title identifier, first domestic release date and its evidentiary source;
* rerelease flag, eligibility decision, exclusion reason, cohort rank, optional eligible rank, and tie flags;
* secondary-source rank/value and a coded conflict note; and
* adjudicator, decision date, and rationale for every nonmechanical decision.

No year is frozen until its top-35 capture, release-year assignments, exclusions, and boundary review are complete. A terminal year is not eligible for freeze until **July 1 of the following year** and all titles that could enter its raw top 35 have completed or substantially completed their domestic runs. The 2025 cohort meets the date condition as of October 19, 2026, but its title-level completion check must still be documented.

After freeze, do not silently refresh dynamic webpages or alter membership. A publisher correction or newly recovered historical table produces a dated amendment dataset, with the original frozen frame retained and the effect on pilot/main membership reported as a sensitivity result. Analysis scripts must point to a versioned manifest rather than live webpages.

## Measurement-break audit

The 1982 change from distributor rentals to theater gross can change rank order because rental terms were not constant. Before full analysis, obtain *Variety* rental tables for 1982–1984 if accessible and compare their eligible top 25 with the Box Office Mojo gross ranking. Report top-10 and top-25 set overlap and Spearman rank correlation for matched titles. Regardless of the result:

* keep `metric_regime` in the analysis data;
* never compare nominal dollar amounts across the boundary;
* include a 1982 regime indicator or segmented-time sensitivity in trend models; and
* report a sensitivity analysis excluding a narrow boundary window (recommended: 1980–1984).

The 2020 pandemic is also a substantive exhibition/distribution shock. It should be flagged for interpretation and sensitivity analysis, not treated as a source error or automatically removed.

## Data-access blockers and feasibility risks

* **Complete *Variety* coverage, especially 1965–1981, may require institutional access.** Free Media History Digital Library/Internet Archive holdings are incomplete for this interval; EIMA/ProQuest or onsite Margaret Herrick Library access may be required.
* **Historical tables are not machine-clean.** OCR can transpose digits, join rows, and omit continuation pages. The plan requires page-image verification and double entry; automated scraping alone is insufficient.
* ***Variety* figures are sometimes estimated, rounded, or deferred.** The protocol preserves estimate flags and source order rather than manufacturing precision.
* **Box Office Mojo has no documented public bulk research export for this use.** Pages are dynamic, and access/licensing terms must be checked before automated collection. Page-by-page lawful snapshots or a licensed IMDb product may be needed.
* **The Numbers may block automated requests and offers a licensed structured data service.** Its [data-services page](https://www.the-numbers.com/data-services) describes the commercial feed. Public pages can support manual audit, but automated capture requires terms review.
* **Comscore's needed historical detail is proprietary.** Public annual press releases are not a substitute for title-level ranks 11–25.
* **Domestic geography is not perfectly stable across sources.** The source-native territory field and regime indicator are therefore mandatory.

If the historical *Variety* tables cannot be lawfully obtained and verified, do not fill 1950–1981 with modern cumulative grosses from The Numbers or incomplete Box Office Mojo pages. The defensible choices are to secure archive access, narrow the study period, or preregister a distinct secondary-source reconstruction with an explicit validation sample. Quietly mixing incomparable lists would make the annual ranks irreproducible.

## Minimum extraction schema

At minimum, the frozen ranking file should contain:

`cohort_year`, `title`, `stable_title_id`, `first_domestic_release_date`, `release_date_source`, `source_regime`, `primary_source_citation`, `source_table_year`, `source_amount_type`, `metric`, `territory_definition`, `amount`, `amount_estimated`, `source_row_order`, `cohort_rank`, `eligible_rank`, `reissue_flag`, `eligibility`, `exclusion_reason`, `tie_flag`, `near_tie_flag`, `secondary_source_citation`, `secondary_rank`, `secondary_amount`, `conflict_code`, `adjudication_note`, `retrieved_at_utc`, `artifact_path`, and `artifact_sha256`.
