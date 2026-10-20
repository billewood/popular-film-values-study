# Frozen pilot success criteria

**Protocol version:** 0.1

**Frozen:** 2026-10-19, before development-film theme extraction

## Purpose and limit

The pilot can establish that the procedure is auditable, mechanically valid, and reproducible enough for cautious descriptive use. With no human theme coders and no independent criterion measure, it cannot establish that model labels are a uniquely correct reading of a film. Passing therefore licenses claims about **source-attributed interpretations**, not unqualified claims about film content, audiences, or U.S. society.

Development films may be used to repair prompts and software. The criteria below are applied once to the untouched six-film validation set after the pipeline is frozen. Any substantive pipeline change after validation begins converts the affected films to development material and requires a new metadata-only validation draw.

## Frozen validation procedure

Each eligible source receives two extraction-and-verification replicates. Replicates use the same frozen model and settings in separate calls and do not receive one another's outputs. Evidence-span variations are collapsed to the source-level unit `(source_id, theme, narrative_segment)` before agreement is measured. A third pass may adjudicate only records proposed by a replicate and may select only an already quoted, exact-matching span; it cannot add evidence or themes.

Empty output is a legitimate result. Sources for which both replicates return no accepted unit are reported as both-empty and excluded from positive-set Jaccard calculations so that abundant negatives cannot inflate agreement.

## Hard gates

All of the following must pass:

1. **Coverage:** one untouched validation film in every historical period meets the frozen four-source minimum, including both contemporary slots and an authoritative synopsis. Substitutions and film replacements remain visible.
2. **Rights:** every processed source has a recorded permission basis compatible with the actual model environment. No credential, restricted full text, or unlicensed corpus is committed publicly.
3. **Schema and provenance:** 100% of accepted records conform to the frozen schema and identify a frozen source, lineage, and locator.
4. **Exact evidence:** 100% of accepted evidence spans match the archived source under the frozen normalization. A verifier may reject but never repair an unsupported record.
5. **Negative controls:** all deliberately corrupted quotations are rejected, and no thematic record is accepted when a source is paired with the identity of a different validation film that the source does not discuss. One of each control type is run per validation source; comparative sources are deranged only to an unmentioned target.
6. **No polarity reversal:** the two replicate film-level results contain no direct `affirmative` versus `critical` reversal for the same film, theme, and segment. Leave-one-source-out results likewise contain no such reversal.
7. **Ending integrity:** every `glamorize_then_punish` result is supported by separate qualifying main-body and ending evidence; external punishment alone never changes the main-body stance.

Failure of a hard gate means revise or stop; it cannot be averaged away by good performance elsewhere.

## Repeatability gates

For each source, compare the replicate sets of accepted `(theme, narrative_segment)` units.

- Median source-level positive-set Jaccard must be at least **0.80**.
- At least **80%** of nonempty source comparisons must have Jaccard at least **0.67**.
- The median within each historical period must be at least **0.67**; a period with no nonempty comparison is reported as not evaluable and triggers revision rather than automatic success.
- Among units found by both replicates, exact salience agreement and exact stance agreement must each be at least **0.80** overall.
- No more than **20%** of the union of proposed source-level units may require the constrained third pass.

Separately aggregate each replicate to film-level scores. Among film/theme/segment cells evidenced by either replicate, exact centrality agreement must be at least **0.80**. Direct polarity reversal is already a hard failure. The late-retribution indicator must agree for every film/theme flagged by either replicate; if neither replicate flags any case, that check is reported as not evaluable rather than passed.

These cutoffs are operational tolerances chosen before theme data exist. They are not estimates of human agreement and will not be retuned to rescue validation results.

## Required sensitivity reports

The following are reported but are not reduced to a single pass/fail number:

- results by contemporary, retrospective, scholarly, and synopsis strata;
- source disagreement and historically differentiated interpretation;
- leave-one-source-out changes in centrality, stance, and late-retribution flags;
- the percentage of corroborated or central cells that depend on one source;
- OCR, source-length, substitution, and access failures by period; and
- both-empty rates and the distribution of source-level Jaccard scores.

Systematic period differences, pervasive one-source dependence, or model/source interactions may still justify revision even when numeric minima pass. The reason must be recorded without reference to whether results support the motivating cultural theory.

## Decision rule

- **Proceed:** every hard gate and repeatability gate passes, no material pipeline change occurred, and no systematic period-specific failure makes the measure misleading.
- **Revise and revalidate:** a fix appears feasible without changing the research question. Freeze the revision, retire affected validation films to development, and draw a new untouched validation set.
- **Stop or narrow:** lawful source coverage, historical ranking construction, or reproducible source-based measurement cannot be achieved for one or more periods without changing the estimand.

Pilot outcomes never enter the later trend analysis and cannot be used to choose breakpoints, theme weights, exclusions, or a preferred historical narrative.
