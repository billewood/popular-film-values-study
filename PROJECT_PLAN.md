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

The following remain open and must be frozen before development-film theme extraction:

1. The language-model provider, exact model/version, decoding settings, and prompts.
2. Machine-agreement and stability thresholds required for a successful pilot.

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
