# Popular Film Values Study

This repository records the prospective methods and project plan for a study of how the moral and motivational themes of popular films have been characterized in published criticism and scholarship.

The project asks a broad, nondirectional question: **How have the motivational and moral worlds attributed to the most popular films in the United States changed over time?** Particular themes include selfishness, consumerism, status, achievement, love, community, care, justice, art, knowledge, religion, spirituality, pleasure, revenge, and autonomy.

## Current status

Version 0.1 was established on **2026-10-19**, before the planned pilot source corpus was collected or analyzed. The pilot is methodological: it will test whether a fully source-based, machine-extracted procedure produces adequately supported and reproducible measurements. It will not test historical trends.

The repository is now public. A public commit identifier has been used to freeze the pilot's year and rank slots before any titles or thematic evidence are retrieved. The evidence ontology, exact-quotation checks, aggregation rules, and late-retribution indicator are implemented with automated tests.

No study participant will watch films and assign thematic codes. Scores will be derived from exact, auditable claims in professional reviews, scholarly criticism, institutional essays, and authoritative plot references.

## Documents

- [METHODS.md](METHODS.md): short pilot Methods section.
- [APPENDIX.md](APPENDIX.md): operational definitions, source rules, extraction procedure, and scoring rules.
- [PROJECT_PLAN.md](PROJECT_PLAN.md): dated decisions, open decisions, milestones, and change-control policy.
- [docs/PILOT_DRAW.md](docs/PILOT_DRAW.md): deterministic year/rank sampling procedure and public seed.
- [docs/BOX_OFFICE_SAMPLING.md](docs/BOX_OFFICE_SAMPLING.md): frozen ranking sources, cohort construction, and title-resolution rules.
- [docs/SOURCE_RETRIEVAL.md](docs/SOURCE_RETRIEVAL.md): frozen source-bundle, neutral-search, rights, and deduplication rules.
- [docs/PILOT_SUCCESS_CRITERIA.md](docs/PILOT_SUCCESS_CRITERIA.md): a priori mechanical, repeatability, and decision gates.

## Reproducibility

The core implementation has no third-party runtime dependencies. Run the test suite with:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

GitHub Actions runs the same tests on every push using Python 3.11 and 3.13.

## Interpretive boundary

The primary estimand is **published interpretation of film content**, not unmediated film content, population-wide audience opinion, or a direct measure of American society. Source silence is treated as missing evidence rather than proof that a theme is absent. Contemporary reception and later scholarly or retrospective interpretation will remain distinguishable in the data.

All substantive changes to the prospective protocol will be documented in later commits rather than silently rewritten.
