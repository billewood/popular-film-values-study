# Pilot Methods

**Protocol version:** 0.1

**Established:** 2026-10-19

## Design

This pilot will develop and test a source-based method for measuring motivational and moral themes attributed to popular films. The measurement target is the interpretation of films documented in professional criticism, scholarship, and institutional film writing. It is not assumed that these sources transparently reveal a film's single correct meaning or represent the opinions of the general audience.

The pilot will include 12 narrative feature films released between 1950 and 2025. Two films will be drawn from each of six historical periods using a reproducible random procedure from films ranked 11–25 in annual domestic theatrical popularity. One film per period will form a six-film development set; the other will form an untouched six-film validation set. Pilot films will remain outside the future main corpus of the ten most popular films per year. The pilot will assess feasibility and measurement performance, not historical change.

## Sources

Each film will receive a fixed five-source bundle: two independent professional reviews published from 30 days before through 365 days after first U.S. commercial release; one later professional, curatorial, or institutional essay; one scholarly article, book chapter, or equivalent substantial analysis; and one authoritative detailed synopsis used only for plot facts. When no scholarly source exists, a second independent retrospective essay may be substituted and the substitution recorded. Films lacking the four-source minimum—both contemporary reviews, the synopsis, and at least one later retrospective or scholarly source—will be replaced according to a prespecified rule.

Sources will be located with title-, year-, director-, and review-based searches. Theme terms will not be used during retrieval. Marketing materials, anonymous blurbs, audience reviews, fan sites, review-aggregator summaries, AI-generated pages, and duplicated or syndicated texts will be excluded. Contemporary reviews and later interpretations will be retained as separate source strata.

## Automated evidence extraction

No human coders will assign film themes. A frozen language-model pipeline will process each source independently and will be restricted to the supplied source text. For every proposed code, it must return an exact supporting passage, source locator, theme, narrative segment, claim type, salience, and stance. An automated verification pass will reject quotations that do not match the archived source and classifications not supported by the quoted passage. The model configuration, prompts, source metadata or hashes, and complete outputs will be archived.

The instrument contains 15 themes: selfishness; consumerism/materialism; status/fame/power; achievement/work/competition; romantic/familial love; friendship/community/solidarity; care/service/sacrifice; justice/duty/public good; art/creativity/beauty; knowledge/truth/discovery; religious conviction/institutions; spiritual/existential meaning; pleasure/adventure; revenge; and freedom/autonomy. These labels have no automatic moral valence. In particular, self-interest, ambition, wealth, pleasure, and autonomy are not sufficient evidence of selfishness or consumerism.

## Scores

For each film and theme, source-attributed centrality will be scored from 0 (*not evidenced in the fixed source corpus*) to 3 (*independently characterized as central by at least two sources*). A zero will not be interpreted as proof of absence. Stance will be classified as affirmative, critical, mixed, or unresolved and will require corroboration from at least two independent sources. A critic's personal approval or dislike will not be treated as evidence of the film's stance.

Main-body and ending evidence will never be combined into a net morality score. A preregistered *glamorize-then-punish* flag will identify themes that sources characterize as important and attractive through the main body but criticized or punished in the ending. External punishment, remorse, behavioral change, and costly repair will remain distinct ending responses.

## Pilot evaluation

Extraction rules may be revised using only the six development films. The source rules, prompt, model configuration, and aggregation code will then be frozen before the six validation films are processed. Evaluation will emphasize source coverage across periods, exact-evidence validity, agreement between independent machine passes, cross-source convergence, missingness, and stability when any single source is removed. Validation-film results will not be used to choose themes, alter thresholds, estimate historical effects, or support conclusions about societal change. Full operational rules appear in [APPENDIX.md](APPENDIX.md).
