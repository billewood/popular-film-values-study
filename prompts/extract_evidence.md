# Evidence extraction prompt — development draft 0.1

You are extracting auditable claims from one supplied publication about one film. Use only the supplied source text. Do not use background knowledge of the film, filmmaker, period, genre, or study hypothesis. Do not try to make the document fit any theme.

Return a JSON array conforming to `schemas/evidence-record.schema.json`. Return `[]` when the source contains no qualifying evidence.

The calling program supplies the target film's stable ID and title. Extract only claims that the supplied passage and context attribute to that target film. Do not trust wrapper metadata when the text concerns another film. If the text does not substantively discuss the target film, return `[]`. A comparative source may qualify, but only its clearly separable claims about the target may be coded.

## Nonnegotiable evidence rule

Every record must contain a short `exact_evidence_span` copied verbatim from the supplied source. Do not paraphrase inside that field. Do not join noncontiguous passages. If the passage does not by itself support the proposed record, emit no record.

## What to extract

Extract only explicit claims concerning one or more of these themes:

1. selfishness
2. consumerism/materialism
3. status/fame/power
4. achievement/work/competition
5. romantic/familial love
6. friendship/community/solidarity
7. care/service/sacrifice
8. justice/duty/public good
9. art/creativity/beauty
10. knowledge/truth/discovery
11. religious conviction/institutions
12. spiritual/existential meaning
13. pleasure/adventure
14. revenge
15. freedom/autonomy

Multiple records may use the same passage only when the passage independently supports each theme.

## Guardrails

- Selfishness requires disregard, exploitation, avoidable harm, or neglect of a meaningful obligation. Self-interest, self-protection, ambition, pleasure, or independence alone is insufficient.
- Consumerism/materialism requires acquisition, consumption, possessions, or market value as identity, success, worth, or the good life. Wealth, products, or an affluent setting alone is insufficient.
- Status, achievement, pleasure, revenge, wealth, and autonomy have no automatic positive or negative stance.
- A critic's approval or dislike is `critic_preference`, not the film's stance.
- A plot fact may support presence, sequence, or consequence, but it does not establish endorsement without explicit interpretive language.
- A factual reference synopsis normally receives `source_stance: unstated`.

## Claim classification

Use `claim_target` to identify whether the passage concerns the film, a character, filmmaker, critic, audience, or society.

Use `claim_type` as follows:

- `plot_fact`: description of an event, action, motive, or outcome;
- `film_theme_attribution`: the source attributes a theme or concern to the film;
- `film_stance_attribution`: the source says how the film presents or evaluates a theme;
- `plot_consequence`: the source explicitly describes reward, punishment, renunciation, remorse, change, repair, or sacrifice;
- `critic_preference`: the author merely expresses personal approval or dislike; or
- `reception_claim`: the source describes how audiences or other critics interpreted the film.

## Narrative segment

- Use `main_body` only when the passage explicitly describes a recurring, sustained, or pre-finale pattern.
- Use `ending` only when it explicitly concerns the finale, final act, climax, resolution, final outcome, comeuppance, renunciation, redemption, atonement, or culminating sacrifice.
- Otherwise use `global_unspecified`. Never infer a segment merely because you know the film.

## Salience

- `1`: explicit but incidental or isolated;
- `2`: explicitly important, recurring, a substantial motive, or a major subplot;
- `3`: explicitly defining, central, the organizing conflict, or the film's thesis.

Do not infer salience from keyword frequency.

## Stance

- `affirmative`: the source attributes celebration, glamorization, romanticization, normalization, reward, desirability, admiration, or fulfillment to the film;
- `critical`: the source attributes criticism, satire, exposure, repudiation, punishment, destructiveness, emptiness, or injustice to the film;
- `mixed`: the source explicitly attributes an ambivalent or contradictory treatment; or
- `unstated`: the source does not explicitly attribute a direction to the film.

## Ending response

For ending evidence only, use one of: `original_pursuit_reinforced`, `external_punishment_only`, `remorse_verbal_recognition`, `changed_behavior`, `costly_repair_sacrifice`, or `ambiguous`. Otherwise use `null`.

Set `explicit_temporal_contrast` to true only when the passage itself contrasts the main presentation with the ending treatment.

## Supplied metadata

The calling program supplies `film_id`, `film_title`, `source_id`, `lineage_id`, and `source_type`. Copy the supplied ID and type fields exactly into every record; `film_title` is identity context and is not an output field. Use the supplied paragraph or page marker for `locator`.
