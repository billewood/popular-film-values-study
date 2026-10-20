# Prospective Project Plan

**Initial record:** 2026-10-19

**Current phase:** Pilot title resolution; no interpretive sources or theme data have been collected in this repository.

## Research objective

Describe how the motivational and moral themes attributed to highly popular films have changed from 1950 through 2025, while allowing the observed evidence—not a presumption of cultural decline—to determine the pattern.

## Decisions established in version 0.1

- The future main sampling target is the ten most popular domestic theatrical films released in each year.
- Pilot films will be sampled from annual ranks 11–25 and excluded from the main corpus.
- The pilot will use 12 films: six for development and six untouched for validation.
- No human research coder will watch films and assign themes.
- All accepted scores must be traceable to exact passages in eligible published sources.
- Contemporary criticism, retrospective criticism, scholarship, and factual plot references are distinct source types.
- Source nonmention is not proof of thematic absence.
- Fifteen themes are specified prospectively.
- Theme centrality and narrative stance are separate variables.
- Main-body presentation and ending response remain separate; final punishment cannot cancel earlier glamorization.
- The pilot will test the method, not the historical hypothesis.
- Pilot films and scores will not be reused in the main historical analysis.

## Protocol decisions and remaining freezes

The following are frozen in the linked implementation documents:

1. Historical box-office source hierarchy and rank reconciliation: `docs/BOX_OFFICE_SAMPLING.md`.
2. Databases, archives, outlet order, neutral searches, and source eligibility: `docs/SOURCE_RETRIEVAL.md`.
3. Film and source replacement rules: `docs/PILOT_DRAW.md` and `docs/SOURCE_RETRIEVAL.md`.
4. Text normalization and duplicate thresholds: `docs/SOURCE_RETRIEVAL.md`; remaining implementation work is tracked as a milestone rather than an open design choice.
5. Copyright, license, storage, and model-processing gates: `docs/SOURCE_RETRIEVAL.md`.
6. Mechanical-validity, machine-repeatability, sensitivity, and go/revise/stop criteria: `docs/PILOT_SUCCESS_CRITERIA.md`.

The following remain open and must be frozen before development-film theme extraction:

1. The language-model provider, exact model/version, decoding settings, and prompts.

These decisions will be committed before the relevant development-film data are processed. They may be informed by logistical testing, but not by whether they produce a preferred substantive pattern.

## Ordered milestones

### Phase 1 — Sampling protocol

- Audit historical popularity sources.
- Freeze source hierarchy and rank-reconciliation rules.
- Generate and archive the pilot candidate frame, random seed, selected films, and replacements.

### Phase 2 — Retrieval protocol

- Freeze archive and outlet hierarchy.
- Implement neutral searches and eligibility checks.
- Test independence, deduplication, metadata capture, and coverage logging without scoring themes.

### Phase 3 — Development set

- Retrieve fixed source bundles for the six development films.
- Refine prompts, evidence schema, theme boundary rules, and aggregation code.
- Establish automated negative controls and exact-quotation verification.

### Phase 4 — Protocol freeze

- Commit the complete prompt, model identifier, source rules, codebook, and analysis code.
- Record all departures from version 0.1 and their methodological reasons.
- Do not inspect validation-film theme results before this freeze.

### Phase 5 — Validation set

- Run the frozen pipeline on six untouched films.
- Report coverage, evidence validity, machine agreement, source convergence, missingness, and leave-one-source-out stability.
- Apply the prespecified go/revise/stop criteria.

### Phase 6 — Main-study preregistration

- Proceed only if the source-based method is sufficiently supported across periods.
- Freeze the main sampling frame and historical models before main-corpus extraction.
- Preserve source-type-specific results and all component scores.
- Phrase conclusions as changes in published interpretations or source-attributed content unless additional evidence justifies a stronger claim.

## Change control

This repository is a prospective record, not an immutable registration. Every substantive change will therefore be made in a new commit and summarized in this file or a dated amendment. Earlier commits will remain in history. Amendments will identify:

- what changed;
- when it changed;
- why it changed;
- what evidence had already been accessed; and
- whether previously processed films or sources became development material.

No force-pushes or history rewrites are planned. A later formal registration may archive a specific commit and its cryptographic identifier in an immutable research registry.

## Amendment log

### 2026-10-19 — Metadata-only draw precedes title resolution

Version 0.1 said the historical ranking hierarchy would be frozen before the film draw. In practice, the public-seed procedure first froze only year/rank coordinates, with no titles attached. The ranking hierarchy was then frozen before those coordinates were resolved to film identities. This preserves the intended blindness to titles, themes, source availability, and likely findings while making the two-stage procedure explicit. At the time of this amendment, no sampled title, interpretive source, or theme output had been retrieved for the pilot.

### 2026-10-19 — Historical projection and cross-table tie rule

Page-level reconstruction revealed that historical *Variety* tables distinguish rentals to date from projected full-playoff rentals and can contain equal rounded projections in different annual tables, where no common publisher order exists. Before assigning any sampled historical title or retrieving any interpretive source, version 0.2 fixed projected ultimate first-run rental as the ranking quantity and applied a public-seed hash only to exact ties lacking a common source order. The full tied block remains visible for sensitivity analysis. This amendment was prompted by raw ranking metadata; no thematic evidence or film-level output had been accessed.

### 2026-10-19 — Historical amount-type break at the 1966 cohort

Further page-level reconstruction showed that *Variety* abandoned its anticipated-revenue column in the table published in January 1968 and thereafter reported rentals to date. Version 0.2 would therefore have made the 1966 and later frames nonconstructible. Version 0.3 uses projected-ultimate rental within the 1950–1965 release cohorts and latest cumulative rental-to-date within the 1966–1981 cohorts, always at the same fixed information cutoff and never mixed within a cohort. The study continues to use only annual ranks across years, and the break is retained as a measurement-regime variable. No sampled historical title had been assigned and no interpretive source or theme output had been accessed when this rule was fixed.

### 2026-10-19 — Cumulative rental rule for the six historical pilot frames

A later table explicitly withdrew a previously published projected-ultimate estimate without replacing it numerically, making the version 0.3 projection rule incomplete for the 1965 cohort. Page inspection confirmed that cumulative/current-to-date rental figures are populated for all potentially rank-relevant rows in each of the six historical pilot cohorts. Version 0.4 therefore uses latest cumulative rentals to date at the common cutoff for all six, never mixing amount types within a cohort. Inspection of the 1950 table also confirmed that this choice cannot be generalized across 1950–1981 without a complete table-method audit; that map will be frozen before main-sample title resolution. No sampled historical title had been assigned and no interpretive source or theme output had been accessed when this rule was fixed.

### 2026-10-19 — Second metadata backup for the 1950–1962 period

The complete 1960 backup frame proved nonconstructible under version 0.4 because no cumulative U.S.–Canada distributor-rental amount for *Spartacus* could be located by the fixed January 31, 1962 cutoff. An October 1961 worldwide theater-gross figure mixes territories and a different monetary construct, while the first located U.S.–Canada rental appears only in January 1963; neither can be substituted. The 1960 failure remains visible. Before any interpretive-source search or theme extraction, the study added the fourth year in the existing public-seed ordering as `backup_2`: 1952, with selected rank 12 and its rank-replacement order derived by the unchanged code. This is a metadata-frame safeguard only and does not add a scored film. No film themes, reviews, scholarly interpretations, or model theme outputs had been accessed when this amendment was made.

### 2026-10-19 — Cohort-specific rule for the 1952 metadata backup

The 1952 annual chart provides final-rental estimates rather than a separate cumulative-to-date column and explicitly defers late releases. Before resolving a 1952 title or accessing any interpretive source, the study froze `projected_ultimate` as that cohort's amount type: the latest like-for-like U.S.–Canada estimate available through January 31, 1954 across the 1952 and 1953 annual tables, with release-year reassignment and no mixing of monetary constructs. The original six historical pilot cohorts retain the cumulative rule; 1960 remains unconstructible. The difference is explicit because the study compares within-year ranks, not dollar amounts across cohorts, and will retain an amount-type indicator. The frame remains unresolved unless every potentially top-35 title has a comparable estimate.

### 2026-10-19 — Clarified four-source minimum

The detailed retrieval protocol requires a four-source minimum consisting of both contemporary reviews, an authoritative synopsis, and at least one later retrospective or scholarly source. The short appendix had stated only two contemporary reviews and two source types, which could admit a bundle without a synopsis or later interpretation. The short methods and appendix now conform to the stricter controlling rule. This correction was made before any interpretive-source retrieval or theme extraction.

### 2026-10-19 — Pre-extraction implementation audit corrections

Mutation testing found that critic-preference and reception records could raise film-theme centrality, a designated synopsis could cast a stance vote, Unicode compatibility folding could make a nonverbatim string pass the quotation check, and verification-result constraints were not identical in code and schema. The implementation now excludes critic and reception claims from film-content scores, prevents synopsis stance votes while retaining factual presence and sequence evidence, uses canonical rather than compatibility Unicode normalization, and enforces consistent verification decisions. Historical pilot amount types and unconstructible slot status are now executable validator rules. These are corrections to make the implementation conform to the already written estimand; no source corpus, thematic output, or validation result had been accessed.
