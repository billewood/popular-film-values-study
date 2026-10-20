# Pilot Methods Appendix

**Protocol version:** 0.2

**Established:** 2026-10-19

**Last amended:** 2026-10-19; see `PROJECT_PLAN.md`

This appendix supplies the operational rules omitted from the short Methods section. Any conflict is resolved in favor of this appendix unless a later dated amendment explicitly says otherwise.

## A. Measurement target

The study produces two related but distinct kinds of evidence:

1. **Source-attributed content claims:** statements that a source makes about what a film depicts, prioritizes, endorses, criticizes, rewards, or punishes.
2. **Reception claims:** a critic's or scholar's own evaluation or interpretation of the film.

These will not be silently combined. Results will be described as published interpretations or source-attributed content. They will not be described as population-wide audience opinion. A source's failure to mention a theme is `not discussed`, not evidence that the theme is absent.

## B. Pilot sampling

The intended historical window is 1950–2025. The six pilot periods are:

1. 1950–1962
2. 1963–1975
3. 1976–1988
4. 1989–2001
5. 2002–2014
6. 2015–2025

Two eligible films will be sampled from each period from positions 11–25 in annual domestic theatrical popularity rankings. The draw will use a recorded random seed and no thematic information. Within each period, one film will be assigned to development and one to validation before source retrieval. A replacement list will be drawn at the same time.

Eligible works are fictional or dramatized narrative feature films. Documentaries, concert films, filmed performances, and rereleases are excluded because the instrument assumes narrative agents, goals, and outcomes. Sequels are eligible, but sources must discuss the sampled film rather than relying on the franchise generally.

The historical box-office source hierarchy and reconciliation procedure must be frozen before film identities are resolved from the metadata-only year/rank draw. Rankings will be based on within-year position; monetary values from different eras will not be treated as directly comparable.

## C. Source bundle and retrieval

The target bundle contains five independent sources per film:

1. two professional reviews published from 30 days before through 365 days after the first United States commercial release;
2. one later professional, curatorial, or institutional essay;
3. one peer-reviewed article, scholarly book or chapter, or comparable academic analysis; and
4. one detailed reference synopsis from an accountable film institution or established reference work.

If no scholarly source is available under the frozen search procedure, a second retrospective professional or institutional essay may be substituted. The substitution is a recorded source-coverage variable. The synopsis may establish actions, sequencing, and outcomes but receives no vote on narrative stance unless it explicitly advances an interpretation.

Retrieval queries may contain only the film title, release year, director, and neutral document terms such as `review`, `criticism`, or `analysis`. They may not contain any of the 15 theme names or theoretically loaded synonyms. Databases, outlet hierarchy, search dates, result ordering, and the number of results screened will be logged before full-text extraction.

Eligible sources must have an identifiable author or responsible institution, publication date, publisher, and substantive discussion of the film. The original full text must be available. The following are excluded:

- advertisements, publicity copy, press kits, or studio-authored promotional material;
- anonymous capsule blurbs lacking substantive interpretation;
- audience reviews, social-media posts, fan wikis, and crowdsourced trope lists;
- search snippets or aggregator summaries without the original review;
- AI-generated or provenance-uncertain pages;
- plot-only recaps, except for the designated reference synopsis; and
- syndicated, copied, or near-duplicate versions of another included source.

Only one item per author and outlet may be used for a film. Computational similarity checks and citation tracing will identify copied, syndicated, or dependent sources. Dependent texts count as one evidentiary lineage rather than independent agreement. Source counts are capped so that canonical or recent films do not receive more weight merely because more has been written about them.

A film is scorable only when at least four independent eligible sources are available, including both contemporary reviews and at least two source types. Otherwise the film is replaced using the presampled list, and the failure remains in the coverage log.

## D. Automated extraction record

The extraction model receives one archived source at a time. It may not browse, retrieve other accounts of the film, or use the film's release year, box-office rank, or hypothesized historical direction. Each proposed record must contain:

```text
film_id
source_id
source_type
exact_evidence_span
page_paragraph_or_url_locator
claim_target
claim_type
theme
narrative_segment
source_salience
source_stance
ending_response
explicit_temporal_contrast
```

Allowed `claim_target` values are film, character, filmmaker, critic, audience, and society. Allowed `claim_type` values are plot fact, film-theme attribution, film-stance attribution, critic preference, and reception claim.

Only film-attributed interpretations and explicit plot consequences may contribute to the film's stance. A critic's personal preference cannot be converted into a film stance. Plot description may support presence or sequencing but cannot by itself establish endorsement.

`narrative_segment` is `main_body`, `ending`, or `global_unspecified`. Main-body and ending labels require explicit temporal evidence. Global claims will not be forced into a segment. References to a finale, final act, climax, resolution, final outcome, comeuppance, renunciation, redemption, atonement, or culminating sacrifice may support an ending classification when the surrounding passage confirms that use.

The pipeline follows a no-quotation-no-code rule. Evidence strings must match the archived source exactly after only predefined normalization of whitespace and typographic punctuation. A separate model pass receives the proposed record and quoted context and may affirm or reject it but may not invent replacement evidence. Disagreements remain unresolved unless a frozen third evidence-constrained pass selects a supported option. Model confidence scores are not evidence.

## E. Theme definitions

1. **Selfishness:** personal wants pursued through disregard, exploitation, avoidable harm, or neglect of a meaningful obligation. Self-interest, self-protection, pleasure, or independence alone is insufficient.
2. **Consumerism/materialism:** acquisition, consumption, possessions, or market status treated as a route to identity, worth, success, or fulfillment. Wealth or products alone are insufficient.
3. **Status/fame/power:** rank, public recognition, prestige, control, or influence pursued as an important end.
4. **Achievement/work/competition:** mastery, productivity, career accomplishment, winning, or competitive success.
5. **Romantic/familial love:** forming, maintaining, repairing, or protecting romantic and family bonds.
6. **Friendship/community/solidarity:** friendship, belonging, reciprocal support, collective identity, or social cohesion.
7. **Care/service/sacrifice:** protecting or benefiting others, especially through sustained service or meaningful cost.
8. **Justice/duty/public good:** fairness, obligation, civic responsibility, righting wrongs, or collective welfare.
9. **Art/creativity/beauty:** creating, preserving, performing, or valuing artistic or aesthetic expression.
10. **Knowledge/truth/discovery:** learning, investigation, truth-seeking, intellectual exploration, or discovery.
11. **Religious conviction/institutions:** explicit faith, doctrine, worship, religious vocation, or institutions affecting motive, conflict, or resolution. A religious setting alone is insufficient.
12. **Spiritual/existential meaning:** purpose, mortality, transcendence, or existential identity outside or beyond organized religion.
13. **Pleasure/adventure:** enjoyment, excitement, novelty, sensual gratification, or adventure pursued as an end.
14. **Revenge:** retaliation or retribution for a perceived injury.
15. **Freedom/autonomy:** self-direction, liberation, independence, or resistance to control.

Multilabel records are allowed only when the quoted passage independently supports every assigned theme. No theme has a predetermined positive or negative stance.

## F. Source-level classification

For each source, theme, and segment, all accepted evidence is collapsed to one salience classification:

- **1 — present/incidental:** the source explicitly identifies the theme or provides an isolated example.
- **2 — important:** the source explicitly describes it as recurring, important, a substantial motivation, or a major subplot.
- **3 — central:** the source describes it as a defining concern, central goal or conflict, organizing principle, or thesis.

Repeated keywords do not establish importance or centrality. Multiple passages in one source remain one source vote.

Source stance is:

- **+1 — affirmative:** the source says the film celebrates, glamorizes, romanticizes, normalizes, rewards, or frames the theme as desirable, admirable, or fulfilling;
- **−1 — critical:** the source says the film criticizes, satirizes, exposes, repudiates, punishes, or frames it as destructive, empty, or unjust;
- **0 — mixed:** the source explicitly describes an ambivalent or contradictory treatment; or
- **NA — unstated:** no film-attributed stance is supported.

If a source provides both affirmative and critical evidence within the same segment, its vote is mixed and both passages are retained.

## G. Film-level aggregation

For each film, theme, and segment, source-attributed centrality is:

- **0 — not evidenced:** no eligible source evidence in the fixed corpus;
- **1 — singly evidenced:** at least one source-level 1, but the criteria below are unmet;
- **2 — corroborated/important:** at least one source-level 3 or at least two independent source-level 2 classifications; or
- **3 — consensus-central:** at least two independent source-level 3 classifications.

Every score will be accompanied by its number of supporting sources. Level 0 is always labeled `not evidenced`, never `absent`.

For stance, let `n+` and `n−` be the numbers of independent directional source votes. Film-level stance is affirmative or critical only when at least two directional sources exist and at least two thirds agree. Otherwise it is mixed/contested or unresolved, with those states retained separately. The underlying vote counts are always preserved.

Contemporary-review results and retrospective/scholarly results will first be calculated separately. Agreement permits a clearly labeled combined summary; disagreement is reported as historically differentiated interpretation rather than averaged away. Films, not individual sources, are the independent units in later historical analyses.

## H. Main-body presentation and ending correction

Main-body and ending evidence are stored as an ordered profile:

```text
[main-body centrality, main-body stance]
    -> [ending centrality, ending stance, ending response]
```

The `glamorize_then_punish` flag is true for a theme only when:

1. main-body centrality is at least 2;
2. main-body stance is affirmative; and
3. ending stance is critical and the evidence identifies an ending consequence.

Ending responses are original pursuit reinforced, external punishment only, remorse or verbal recognition, changed behavior, costly repair or sacrifice, and ambiguous. These are categorical, not a scale of moral worth. External punishment without demonstrated internal change remains `external punishment only`; it does not retroactively change the main body's stance.

Primary historical analyses, if the method passes validation, will report main-body measures. Ending measures and reversal patterns will be reported separately. No opaque net morality score will be constructed.

## I. Pilot development, validation, and decision rules

Only the six development films may be used to refine retrieval instructions, prompts, labels, and aggregation code. After those revisions, the complete pipeline is versioned and frozen before processing the six validation films.

Numeric mechanical-validity and repeatability gates are frozen separately in `docs/PILOT_SUCCESS_CRITERIA.md`. They exclude shared no-evidence cells from positive-agreement metrics and cannot be retuned after theme extraction begins.

The validation report will include:

- eligible-source coverage and substitutions by historical period;
- percentage of accepted records with exact-match evidence;
- agreement between independent extraction/classification passes;
- number of source-supported, contested, unresolved, and not-evidenced scores;
- agreement and disagreement across contemporary and later source strata;
- leave-one-source-out stability of film-level results;
- false acceptance on deliberately mismatched film/source negative controls; and
- processing failures associated with OCR quality, source length, publication type, or period.

The following trigger revision rather than a successful pilot:

- any accepted claim lacking verifiable source evidence;
- systematic inability to assemble the minimum source bundle in one or more periods;
- source or model disagreement that makes directional stance unstable;
- false attribution of a source's personal preference to the film;
- systematic differential missingness or extraction failure by period; or
- a material change to the source rules, ontology, prompt, or aggregation procedure after validation has begun.

If the pipeline changes after validation begins, the affected validation films become development material. A later untouched sample is required before the changed procedure is described as validated.

Pilot films and results will not enter the main historical analysis. The pilot will not determine temporal breakpoints, theme weights, exclusions, or substantive hypotheses according to whether they favor the motivating theory.
