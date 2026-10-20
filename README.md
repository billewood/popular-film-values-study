# Popular Film Values Study

This repository records the prospective methods and project plan for a study of how the moral and motivational themes of popular films have been characterized in published criticism and scholarship.

The project asks a broad, nondirectional question: **How have the motivational and moral worlds attributed to the most popular films in the United States changed over time?** Particular themes include selfishness, consumerism, status, achievement, love, community, care, justice, art, knowledge, religion, spirituality, pleasure, revenge, and autonomy.

## Current status

Version 0.1 was established on **2026-10-19**, before the planned pilot source corpus was collected or analyzed. The pilot is methodological: it will test whether a fully source-based, machine-extracted procedure produces adequately supported and reproducible measurements. It will not test historical trends.

The repository is now public. A public commit identifier was used to freeze the pilot's year and rank slots before any titles or thematic evidence were retrieved. The 1982–2024 derived ranking frames and modern pilot-title resolutions are versioned in [`data/box_office`](data/box_office); their source-page artifact freeze is still incomplete because the original HTML responses were not retained. Reconstruction of the historical *Variety* frames is also in progress. No interpretive-source search or theme extraction has begun.

The evidence ontology, exact-quotation checks, aggregation rules, `glamorize_then_punish` flag, ranking audits, and metadata-only source-bundle controls are implemented with automated tests. The source controls validate the recorded search slots, date and length rules, source independence, archive-coverage dispositions, and item- and environment-level processing permissions before any text may enter the extraction pipeline. They establish structural completeness and internal consistency; archive holdings, rights, and license assertions still require external verification. The end-to-end adapter that will derive extraction identities and the validation manifest from frozen bundles remains a required pre-extraction milestone.

No study participant will watch films and assign thematic codes. Scores will be derived from exact, auditable claims in professional reviews, scholarly criticism, institutional essays, and authoritative plot references.

## Documents

- [METHODS.md](METHODS.md): short pilot Methods section.
- [APPENDIX.md](APPENDIX.md): operational definitions, source rules, extraction procedure, and scoring rules.
- [PROJECT_PLAN.md](PROJECT_PLAN.md): dated decisions, open decisions, milestones, and change-control policy.
- [docs/PILOT_DRAW.md](docs/PILOT_DRAW.md): deterministic year/rank sampling procedure and public seed.
- [docs/BOX_OFFICE_SAMPLING.md](docs/BOX_OFFICE_SAMPLING.md): frozen ranking sources, cohort construction, and title-resolution rules.
- [docs/SOURCE_RETRIEVAL.md](docs/SOURCE_RETRIEVAL.md): frozen source-bundle, neutral-search, rights, and deduplication rules.
- [docs/PILOT_SUCCESS_CRITERIA.md](docs/PILOT_SUCCESS_CRITERIA.md): a priori mechanical, repeatability, and decision gates.
- [`data/box_office`](data/box_office): frozen modern ranking rows, cross-source audit fields, exclusions, and resolved pilot slots.
- [`templates`](templates): synthetic, metadata-only examples of an archive access manifest, retrieval log, and frozen source bundle.

## Reproducibility

The core implementation has no third-party runtime dependencies. Run the test suite with:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

GitHub Actions runs the same tests on every push using Python 3.11 and 3.13.

Audit a completed metadata-only source bundle with:

```bash
python scripts/audit_source_bundle.py \
  --manifest path/to/archive-access-manifest.json \
  --retrieval-log path/to/source-retrieval-log.json \
  --bundle path/to/frozen-source-bundle.json
```

The files in `templates/` are synthetic fixtures, not retrieved study sources or credentials. Full source text and access secrets are forbidden in these public metadata records.

## Interpretive boundary

The primary estimand is **published interpretation of film content**, not unmediated film content, population-wide audience opinion, or a direct measure of American society. Source silence is treated as missing evidence rather than proof that a theme is absent. Contemporary reception and later scholarly or retrospective interpretation will remain distinguishable in the data.

All substantive changes to the prospective protocol will be documented in later commits rather than silently rewritten.
