# Prospective Project Plan

**Initial record:** 2026-10-19

**Current phase:** Protocol development; pilot data not yet collected in this repository.

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

## Open decisions that must be frozen before pilot sampling

1. Historical box-office source hierarchy and rules for reconciling conflicting ranks.
2. Exact databases, archives, and outlet order used for source retrieval.
3. Replacement rules for inaccessible films or insufficient source coverage.
4. The language-model provider, exact model/version, decoding settings, and prompts.
5. Text-normalization and near-duplicate-detection procedures.
6. Machine-agreement and stability thresholds required for a successful pilot.
7. Storage rules for copyrighted source text; shareable outputs may contain metadata, lawful short excerpts, and hashes rather than full text.

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
