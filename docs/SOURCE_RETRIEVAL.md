# Frozen Review and Scholarship Retrieval Protocol

**Protocol version:** 0.1

**Frozen:** 2026-10-19

**Study window:** films released from 1950 through 2025

**Applies to:** pilot development and validation films; later use in the main study requires a dated confirmation that archive access and licenses have not changed

## 1. Purpose and interpretive boundary

This document operationalizes Section C of `APPENDIX.md`. It governs how published sources are found, selected, acquired, deduplicated, and stored before any theme extraction occurs.

The study measures **themes attributed to films in eligible published sources**. It does not treat reviews or scholarship as transparent measurements of a film's one correct meaning, a representative sample of audience opinion, or a direct measure of United States society. Retrieval operators and software must not search for, prefer, or reject a source because of the thematic position it takes.

The procedure is deliberately source-blind with respect to the study's 15 themes:

- queries use bibliographic identifiers and neutral document-type words only;
- sources are selected by a frozen hierarchy and tie-break rules;
- source silence is `not discussed`, never evidence that a theme is absent;
- contemporary reception, later criticism, scholarship, and factual synopsis remain separate source strata; and
- a bibliographic hit fills no slot until complete text is lawfully available for the extraction workflow.

This is a **no-human-theme-coder** design, not a promise of unattended retrieval. Authorized staff or librarians may authenticate to databases, obtain an item, and verify bibliographic facts. They may not assess themes, inspect model theme outputs while selecting sources, or choose among eligible sources on substantive grounds.

## 2. Frozen source bundle

### 2.1 Source roles

The target bundle for each film has five independent source lineages.

| Slot | Required source | Temporal window | Function in analysis |
|---|---|---|---|
| `C_TRADE` | One contemporary professional film-trade review | 30 days before through 365 days after first U.S. commercial release | Release-era interpretation |
| `C_GENERAL` | One contemporary professional general-press review | Same window | Release-era interpretation from a non-trade outlet |
| `R_LATER` | One later professional, curatorial, or institutional essay | At least 730 days after first U.S. commercial release | Retrospective interpretation |
| `S_ACADEMIC` | One scholarly article, book chapter, or equivalent substantial academic analysis | Published on or after first U.S. commercial release; items within 365 days are flagged `contemporary_scholarship` | Scholarship |
| `P_SYNOPSIS` | One authoritative detailed synopsis | No publication-date restriction | Plot facts and sequence only |

`P_SYNOPSIS` receives no vote on a film's stance unless the source itself explicitly makes an interpretation and independently qualifies for an interpretive slot. The same document cannot fill two slots.

If no eligible `S_ACADEMIC` source exists after the complete scholarly search, a second independent retrospective source, `R_LATER_2`, replaces it. This is the only routine cross-slot substitution. It is recorded as `scholarship_substitution = true` and is never described as scholarly evidence.

### 2.2 Release-date anchor

The anchor is the earliest documented **public, ticketed commercial opening in the United States**, including a platform opening in New York or Los Angeles. Festival, market, press, cast-and-crew, test, and invitation-only screenings do not establish the anchor.

Release dates are resolved in this order:

1. AFI Catalog premiere or release information;
2. Film Index International;
3. the distributor's dated release record corroborated by a contemporary trade source; and
4. two concordant authoritative reference records.

The chosen date, all conflicting dates, sources consulted, and resolution rule are logged. The 30-day lead is a fixed exception to the general 12-month contemporary rule so that embargo-lift reviews immediately preceding release are not lost. A review tied only to a substantially earlier festival screening is ineligible even if it falls inside the calendar window.

### 2.3 Minimum analyzable bundle

A film is source-scorable only if it has all of the following:

1. `C_TRADE` and `C_GENERAL`, from different authors, outlets, and lineages;
2. at least one eligible later interpretive source, `R_LATER` or `S_ACADEMIC`; and
3. `P_SYNOPSIS`.

Thus, the hard minimum is four sources and three independent interpretive lineages. The five-source target remains the default. Missing a target slot is a reported coverage outcome, not permission to search selectively for more favorable material.

## 3. Access preflight: what can actually be automated

Before pilot films are searched, create a dated `archive_access_manifest` recording institutional subscriptions, personal subscriptions, API keys, text-and-data-mining permissions, export restrictions, and the person or institution authorized to use each resource. A resource marked unavailable in that manifest remains unavailable for the entire frozen run. Credentials and subscription tokens are never committed to the repository.

The following table distinguishes discovery from lawful full-text acquisition. “Automatable” means that the provider documents an API, bulk dataset, or licensed text-mining route; it does not authorize bypassing authentication, paywalls, rate limits, robots controls, or contract terms.

| Resource | Intended use and documented coverage | Discovery automation | Full-text acquisition and processing |
|---|---|---|---|
| **Media History Digital Library / Lantern** | Historical film trade papers and magazines. UW–Madison describes it as a free archive of millions of pages and reports that the large majority of its materials are public domain. | **Yes.** Use the documented [Lantern API](https://lantern.mediahist.org/api), with caching, backoff, and a descriptive user agent. | **Yes for item text actually supplied by the archive, subject to the item-level rights statement.** Volume scans and OCR are also linked through the Internet Archive. Lantern is page-level rather than reliable article-level indexing, so page boundaries and bylines still require bibliographic verification. See [UW–Madison's project description](https://wcftr.commarts.wisc.edu/index.php/all-projects/media-history-digital-library/). |
| **Library of Congress Chronicling America** | Open historical U.S. newspapers; useful principally for 1950–1963 fallback coverage in this study. | **Yes.** The Library documents a public [loc.gov API](https://www.loc.gov/apis/additional-apis/chronicling-america-api/), text services, IIIF, and bulk OCR. No API key is required; responsible rate limiting is expected. | **Yes where supplied, with OCR-quality checks.** The Library warns that OCR is imperfect and publishes [technical and bulk-data documentation](https://www.loc.gov/collections/chronicling-america/about-this-collection/technical-information/). Item rights must still be checked; the collection's [rights statement](https://www.loc.gov/collections/chronicling-america/about-this-collection/rights-and-access/) notes possible third-party material. |
| **The New York Times Article Search / Archive APIs** | Metadata discovery for NYT articles from 1851 forward. | **Yes for metadata.** The [Article Search specification](https://github.com/NYTimes/public_api_specs/blob/master/article_search/article_search_v2.json) returns headlines, abstracts or lead paragraphs, URLs, dates, bylines, and other metadata—not a general full-text research feed. An API key is required. | **No general API route for full article bodies.** Full text requires an NYT subscription, TimesMachine, or a licensed database. NYT documents TimesMachine coverage for 1851–2002 and subscription/download limits in its [archive help](https://thenewyorktimeshelpcenter.helpjuice.com/115014772767-New-York-Times-Archived-Articles-and-TimesMachine). Do not automate PDF acquisition or upload subscriber text to an external model without permission. |
| **ProQuest Historical Newspapers / U.S. Major Dailies** | Full-page and full-text newspaper archives, including NYT and major fallback outlets, depending on institutional holdings. | **Ordinary ProQuest search is access-controlled and must not be scraped.** Metadata export may be performed interactively under the institutional license. | **Only with authorized access.** Normal subscriptions permit limited research downloads, not systematic harvesting. Automated text work requires an institutional **TDM Studio** entitlement or written permission. ProQuest describes rights-cleared datasets in its [TDM Studio guide](https://about.proquest.com/globalassets/proquest/files/toolkits/tdm-quick-guide-2022-oct.pdf) and limits mining/export in its [TDM Studio terms](https://about.proquest.com/en/about/supplemental-terms-of-use-tdm-studio/). |
| **ProQuest Entertainment Industry Magazine Archive (EIMA)** | Trade and consumer magazines. ProQuest documents Variety 1905–2000 and Boxoffice 1920–2000 in one collection, and The Hollywood Reporter 1930–2015 in another. | **Subscription/manual**, unless TDM Studio or another licensed interface is available. | **Subscription/manual or licensed TDM only.** See ProQuest's [EIMA content documentation](https://proquest.libguides.com/eima/content) and [Hollywood Reporter Archive description](https://pq-static-content.proquest.com/collateral/media2/documents/brochure-hollywoodreporter.pdf). |
| **EBSCO Film & Television Literature Index with Full Text** | Film scholarship and trade reviews. EBSCO's product documentation includes Variety film reviews dating to 1914. | **Subscription/manual.** An EBSCO API may be used only if the institution's agreement enables it. The public website is not a bulk-download endpoint. | **Not usable in the planned model pipeline under EBSCO's current standard agreement without an amendment or written permission.** The standard agreement expressly bars use of database content with AI or machine-learning tools. Consult the institution's executed agreement, the current [EBSCO license](https://legal.ebsco.com/license-agreement), and the [database description and title list](https://about.ebsco.com/resources/film-television-literature-index-full-text). EBSCO remains a discovery route unless permission is documented. |
| **FIAF International Index to Film Periodicals Plus** | Film-specific scholarly and critical discovery. ProQuest documents indexing from 1972 onward and full text for a subset of journals. | **Subscription/manual**, or licensed ProQuest TDM. Z39.50/OpenURL support is not a grant of bulk full-text rights. | **Full text only where the subscription supplies it and the license permits processing.** See [FIAF/ProQuest documentation](https://about.proquest.com/en/products-services/fiaf/). |
| **AFI Catalog / Film Index International** | Release facts and synopsis. AFI is strongest for U.S. films; ProQuest describes comprehensive AFI coverage through 1975 and full or short records thereafter. Film Index International covers films from more than 170 countries and includes synopses. | The public AFI web catalog is searchable but has no documented public research API. ProQuest searching requires subscription. | **Manual/browser acquisition unless an authorized licensed route exists.** See [AFI Catalog](https://aficatalog.afi.com/), [ProQuest's AFI description](https://about.proquest.com/en/products-services/american_film_inst/), and [Film Index International](https://about.proquest.com/en/products-services/film_index_internat/). |
| **Crossref** | DOI and scholarly metadata discovery. | **Yes.** Its open [REST API](https://www.crossref.org/documentation/retrieve-metadata/rest-api/access-and-authentication/) supports bibliographic search; use the polite pool, cache responses, and obey returned rate limits. | **No.** Crossref metadata does not itself confer access to an article or chapter. |
| **OpenAlex and Unpaywall** | Scholarly metadata and lawful open-access-location discovery. | **Yes.** Use the [OpenAlex API](https://help.openalex.org/api/) and its current authentication/rate-limit rules. For a known DOI, the [Unpaywall API](https://data.unpaywall.org/products/api) can return OA locations; its general search endpoint was retired in 2026. | **Only the linked copy whose license or repository terms permit use.** An OA-location field is a lead, not proof that every linked file may be redistributed. Record version and license. |
| **JSTOR** | Scholarly articles, books, and reviews. | Metadata search may be done through the normal interface. It must not be scraped. | **Only through ordinary authorized downloads or an approved dataset request.** JSTOR documents a [text-analysis request workflow](https://support.jstor.org/hc/en-us/articles/32479181127575-JSTOR-Text-Analysis-Support-Getting-Started) and separate [text-analysis terms](https://about.jstor.org/terms/text-analysis-support/). Approval and export conditions are project-specific. |
| **Original outlet and institutional websites** | Current reviews and later essays from Variety, THR, BFI/Sight and Sound, Film Comment, MoMA, Library of Congress, Academy Museum, AFI, Criterion, and major newspapers. | **Usually metadata/manual only.** Use an official feed or API if one is documented. Otherwise, conduct low-volume browser retrieval; do not infer permission to crawl from public visibility. | Public HTML may be saved and processed only when the site's terms and copyright status allow it. Paywalled or subscriber text requires authorized access and compatible processing rights. |
| **Google Scholar, Google Books, WorldCat, and library catalogs** | Discovery and location finding only. | Scholar has no supported public bulk-search API and is **manual-only** here. Books and catalog APIs may supply metadata or preview status. | Snippets, search previews, and catalog records are never full text and cannot fill a source slot. Obtain the work lawfully from the publisher, an OA repository, or a library. |

The practical consequence is that a fully unattended pipeline is not assumed. Open archival retrieval, metadata discovery, logging, hashing, and duplicate detection can be automated. Institutional authentication, interlibrary-loan requests, print or microfilm consultation, and some full-text acquisition require authorized human access. If the license does not permit the acquired text to be supplied to the extraction system, the item is **access-ineligible** even when a person can read it.

## 4. Fixed outlet and database hierarchy

### 4.1 Contemporary trade review: `C_TRADE`

Search outlets in this order and stop at the first outlet that yields an eligible review:

1. **Variety**
2. **The Hollywood Reporter**
3. **Boxoffice**
4. **Motion Picture Daily**
5. **Film Daily**

An outlet is searched only for dates in which the access manifest shows issue coverage. Do not count a news brief, box-office notice, advertisement, production item, or capsule listing as a review. Variety's own subscription materials describe an editorial archive from 1905 forward, while EBSCO and ProQuest offer additional licensed routes; access is not assumed merely because the archive exists.

For each outlet, use the access route in this order:

1. open, provider-supported archive or API;
2. licensed film-specific or periodical database;
3. licensed newspaper/magazine database;
4. original publisher archive; and
5. a physical or microfilm copy obtained through a library.

The route changes access, not source identity. Two copies of the same Variety review remain one source.

### 4.2 Contemporary general-press review: `C_GENERAL`

Search outlets in this order and stop at the first eligible review:

1. **The New York Times**
2. **Los Angeles Times**
3. **The Washington Post**
4. **Chicago Tribune**
5. **The Christian Science Monitor**
6. **Time**
7. **Newsweek**

If none yields an eligible review, search one major daily newspaper in the city of the film's first U.S. commercial engagement. The city paper must be identified in the access manifest before its content is inspected. If two papers qualify, choose the one with the longer continuous archival run over the study window; break a tie alphabetically by publication title.

Chronicling America is a fallback discovery route, not a substitute outlet category. Likewise, ProQuest is an access platform rather than a source.

### 4.3 Later professional, curatorial, or institutional essay: `R_LATER`

Search the following tiers in order. Search every outlet within a tier before moving to the next tier. If more than one eligible item exists in the first successful tier, apply the tie-break rules in Section 6.5.

**Tier 1 — nonprofit or public film institutions**

1. BFI / *Sight and Sound*
2. Film at Lincoln Center / *Film Comment*
3. Museum of Modern Art
4. Library of Congress, including National Film Registry essays
5. Academy Museum or Academy of Motion Picture Arts and Sciences
6. American Film Institute

**Tier 2 — professional retrospective criticism**

1. *The New York Times*
2. *Los Angeles Times*
3. *The Washington Post*
4. *The New Yorker*
5. Chicago Reader or RogerEbert.com
6. *Time*

**Tier 3 — named-author commissioned edition essays**

1. Criterion Current
2. another established home-video or repertory publisher's signed analytical essay

Tier 3 sources are flagged `commercial_curatorial = true`. Product descriptions, sales copy, unsigned program notes, and press-kit text remain excluded.

### 4.4 Scholarship: `S_ACADEMIC`

Search discovery systems in this order:

1. FIAF International Index to Film Periodicals;
2. Film & Television Literature Index;
3. JSTOR;
4. Project MUSE;
5. Crossref and OpenAlex, followed by Unpaywall for a lawful OA location;
6. MLA International Bibliography;
7. WorldCat and the local library catalog for scholarly books and chapters;
8. Google Scholar as a manual discovery backstop only.

An index record, abstract, citation, book review, search snippet, or Google Books preview cannot fill the slot. Full text of the relevant analysis must be available. Discovery-system order determines search order, not evidentiary weight.

Search systems sequentially. Stop once a priority-1 or priority-2 scholarly form below has been lawfully acquired and passes independence checks. If only lower-priority candidates have been found, continue through the remaining accessible systems, deduplicate the candidate pool, and then apply the priority and tie-break rules. The substitution search is complete only after all accessible systems have been attempted or a priority-1/2 source has qualified.

Eligible scholarly forms, in priority order, are:

1. a peer-reviewed article devoted primarily to the sampled film;
2. a scholarly book chapter devoted primarily to it;
3. a peer-reviewed comparative article with a clearly separable substantial analysis of it;
4. a scholarly book section with at least 1,000 words or three continuous pages substantially analyzing it; and
5. a completed doctoral dissertation chapter meeting the same substantial-analysis rule.

Conference abstracts, slide decks, syllabi, undergraduate papers, commercial study guides, encyclopedia stubs, and unpublished generative-AI output are excluded. If no item qualifies after the capped search, use `R_LATER_2` rather than lowering the academic standard.

### 4.5 Detailed synopsis: `P_SYNOPSIS`

Search in this order:

1. AFI Catalog;
2. Film Index International;
3. BFI film records or another national film institute's accountable catalog;
4. a signed or editorially accountable synopsis in an established film reference work, such as AllMovie; and
5. a published scholarly film encyclopedia with a sufficiently detailed plot account.

Wikipedia, IMDb user plot summaries, TMDB, fan wikis, crowdsourced recaps, studio pressbooks, distributor marketing synopses, and generative-AI summaries are excluded. A short logline does not qualify.

## 5. Neutral query protocol

### 5.1 Allowed query components

Let:

- `T` be the exact U.S. release title;
- `TA` be a documented alternate or original-language title;
- `Y` be release year;
- `D` be the director's surname; and
- `W` be the applicable source window.

Queries may contain only `T`, `TA`, `Y`, `D`, neutral medium terms (`film`, `movie`, `cinema`, `motion picture`), and neutral document terms (`review`, `criticism`, `essay`, `analysis`, `synopsis`). They may use outlet, database, date, language, and document-type filters.

Queries must not contain a study-theme label, a synonym or antonym of a theme, a character motivation, a moral evaluation, an ending event, or a hypothesized social trend. Prohibited examples include `greed`, `selfish`, `altruism`, `consumerism`, `materialism`, `love`, `sacrifice`, `justice`, `punished`, and `capitalism`.

### 5.2 Query sequence for reviews and later essays

Within each outlet, execute these queries in order and stop after the first query that produces an eligible source:

1. `"T"` with outlet and date filters;
2. `"T" D` with the same filters;
3. `"T" (film OR movie) review` for contemporary slots, or `"T" (film OR movie) (essay OR criticism OR analysis)` for later slots;
4. repeat 1–3 with each documented `TA`; and
5. for evident OCR failure only, remove a leading article from `T` or use a wildcard/fuzzy match on title tokens plus `D`.

OCR relaxation is neutral and must be logged as such. It may not add plot words as search hooks. For titles of three characters or fewer, common dictionary words, or known remakes, `D` and `Y` are mandatory.

For a general web search used only to locate an original outlet page, add `site:outlet-domain` to the same query. Search-engine snippets are never acquired evidence.

### 5.3 Query sequence for scholarship

Use fielded search where the database permits it:

1. exact `T` in title, abstract, subject, or full text, plus `D`;
2. exact `T` plus `(film OR cinema)`;
3. `TA` plus `D`; and
4. `TA` plus `(film OR cinema)`.

The words `review`, `criticism`, and `analysis` may be added only as document-type terms, not as theoretical filters. Apply English-language and full-text filters only after recording the unfiltered result count. A “peer reviewed” database flag is useful metadata but must be verified from the journal or publisher where ambiguous.

### 5.4 Query sequence for synopsis

Search `T`, then `T + D`, then documented alternate titles. Select a record only after matching director, release year, and production identity. Remakes, same-title films, rereleases, and franchise installments must be disambiguated explicitly.

### 5.5 Search cap and logging

For every query, record:

```text
query_id
film_id
slot
resource_or_outlet
access_route
exact_query
filters
sort_order
query_timestamp_utc
result_count_reported
results_screened
candidate_ids_and_ranks
stop_reason
```

Screen all results when there are 50 or fewer. If there are more than 50, screen the first 50 in the provider's documented order and record that order. For a general web search, screen at most the first 20 results. Do not continue because the first eligible source lacks a desired theme. Search results and exclusions are logged before the source is sent to the extraction model.

## 6. Eligibility, selection, and exclusion

### 6.1 Requirements for every source

Every included source must have:

- a named author, stable critic pseudonym/initials, or accountable publishing institution;
- a publication date at the precision needed for its source window;
- an identifiable publisher or outlet;
- a stable URL, DOI, database document ID, ISBN/page range, or archive page identifier;
- complete text, not merely metadata, abstract, snippet, or preview;
- substantive discussion of the sampled film;
- English-language text or an authorized published English translation; and
- rights and access conditions compatible with the frozen extraction environment.

An anonymous historical trade review may qualify under the outlet's institutional authorship, but its `author_id` is the outlet and no second anonymous item from that outlet may count independently.

### 6.2 Minimum substantive length

Length is a screening aid, not evidence of thematic importance.

- Contemporary review: at least 200 words of editorial review text about the sampled film.
- Later essay: at least 600 words total, with at least 400 words substantially about the sampled film.
- Academic comparative work or book section: at least 1,000 words or three continuous pages substantially about the sampled film.
- Synopsis: at least 300 words or an equivalently detailed scene-sequence account.

Headers, menus, captions, advertisements, bibliographies, boilerplate, and reader comments do not count. A 100-to-199-word contemporary source can qualify only when the provider labels the item a review and the scan or publisher page shows it is the complete editorial item rather than a clipped excerpt. The exception is declared before theme extraction and reported by era. A review under 100 words never qualifies.

### 6.3 Exclusions

Exclude:

- advertisements, publicity copy, press kits, distributor synopses, and studio-authored promotional material;
- anonymous capsule blurbs and rating-only entries;
- audience reviews, social posts, podcasts without a verified transcript, personal fan sites, fan wikis, and trope databases;
- search snippets, abstracts, previews, and aggregator summaries without original full text;
- plot-only recaps except the designated synopsis slot;
- AI-generated or provenance-uncertain pages;
- a review of a different release, remake, franchise generally, home-video edition, or stage adaptation;
- interviews that report only a filmmaker's intentions without independent analysis;
- translated or reposted text whose original source cannot be identified;
- inaccessible items, pirated copies, or files obtained by circumventing a technical control;
- sources whose license does not permit the planned processing environment; and
- exact, syndicated, copied, substantially revised, or near-duplicate versions of an already selected source lineage.

### 6.4 Bibliographic screening may not become theme coding

Retrieval staff may read only enough to establish that the item is complete, is about the correct film, is the correct document type, and meets the substantive-length rule. They do not label values, motivations, stance, salience, endings, or evidence passages. If determining document type would require a thematic judgment, mark the candidate `eligibility_ambiguous` and use the next objectively eligible item.

### 6.5 Deterministic choice among multiple eligible items

Apply these rules without inspecting thematic content:

- **Contemporary review:** choose the review with publication date closest to the release-date anchor; ties go to the earlier timestamp, then lexicographically by normalized article title.
- **Later essay:** choose the highest successful tier, then the earliest eligible publication date; ties are broken by normalized author surname and article title.
- **Scholarship:** choose the highest eligible form in Section 4.4, then the earliest publication date; ties are broken by DOI, ISBN/page start, or normalized title in that order.
- **Synopsis:** choose the first eligible source in the hierarchy.

Once a slot is filled, lower-ranked candidates remain in the retrieval log but are not processed for themes. The protocol does not select the “best,” most detailed, most favorable, or most frequently cited interpretation after reading it.

## 7. Independence, deduplication, and lineage

### 7.1 Independence rules

For a given film:

- include at most one source per author;
- include at most one source per outlet;
- two editions, URLs, database copies, translations, or reprints of the same text are one source;
- a wire-service, syndicated, or shared press-pool text is one lineage regardless of the number of publishers;
- an author's later revised or republished version of their own essay is one lineage; and
- a source passage that merely quotes or paraphrases another selected source does not independently corroborate that claim.

Corporate ownership alone does not automatically merge distinct editorial sources, but `parent_company_at_publication` is recorded. A sensitivity analysis may collapse commonly owned outlets. Shared byline, text, wire credit, or explicit republication always establishes dependence.

### 7.2 Automated duplicate checks

For every acquired text:

1. retain an immutable raw-file SHA-256 hash where storage is permitted;
2. create a normalized text for comparison using Unicode NFKC, lowercase, normalized quotation marks, collapsed whitespace, and removal of navigation/boilerplate identified by a frozen extractor;
3. compute a SHA-256 hash of normalized text;
4. compute token 5-shingle MinHash similarity against all candidates for that film; and
5. compare author, outlet, title, date, wire credit, canonical URL, DOI, and citations.

Classification rules:

- identical raw or normalized hash: `exact_duplicate`;
- estimated 5-shingle Jaccard similarity at least 0.80: `near_duplicate_same_lineage` unless clearly caused by a common short synopsis embedded in otherwise independent works;
- similarity from 0.60 through 0.799: `lineage_review_required`; and
- lower similarity does not override shared byline, syndication credit, or explicit republication evidence.

Lineage review is limited to provenance and textual derivation and is conducted before theme outputs exist. If dependence cannot be resolved, treat the candidates conservatively as one lineage and replace the lower-ranked item.

### 7.3 Scholarly citation dependence

Citing the same earlier work does not by itself make two scholarly analyses duplicates. However, text or claims explicitly attributed to the same prior critic or scholar are derivative for corroboration. Store cited-source identifiers and attribution spans so the later aggregation stage can distinguish independent interpretation from repeated authority.

Each included item receives a stable `lineage_id` based on the earliest identified original publication, not the database copy used to acquire it.

## 8. Bundle completion and replacement rules

### 8.1 Source replacement within a film

If a selected candidate fails acquisition, rights review, completeness, identity matching, or duplicate checks, take the next candidate under the same slot's frozen hierarchy and tie-break rules. Record both the rejected candidate and one of these reason codes:

```text
not_about_sampled_film
wrong_document_type
outside_date_window
incomplete_text
insufficient_length
missing_authorship_or_date
duplicate_or_dependent
no_processing_rights
access_failure
ocr_unusable
other_predefined
```

Do not replace a source because it contains no codeable themes, disagrees with another source, is difficult for the model, or would lower a film's score.

### 8.2 Film replacement

The public draw fixes one development slot, one validation slot, and one usable backup-year slot per historical period. Each slot also has a complete, frozen ordering of ranks 11–25. The within-year rank order is used only to replace a work that fails the narrative-feature eligibility rule or whose cohort identity remains unresolved. The original 1960 backup for the 1950–1962 period is retained as an `unconstructible` metadata frame and is skipped mechanically; its public-seed successor, 1952, is the usable backup for that period. If an otherwise eligible development or validation film fails the minimum source bundle after the complete frozen search, record a film-level failure and move to that period's usable presampled backup-year slot, beginning with its selected rank and then applying its frozen within-year order for content eligibility only.

The single usable backup-year slot is shared by the period. If both primary films in a period fail source coverage, or if the usable backup film also fails source coverage, retrieval for that period stops. If only one primary film fails, the backup assumes that film's development or validation assignment. Replacement preserves the historical period and the original rank-11-to-25 sampling frame. No matching on observed themes is permitted.

The study does not widen a date window, lower source standards, add theme queries, or choose a convenient film. Exhausting the frozen replacement rule triggers a dated protocol amendment and a fresh metadata-only draw before any affected validation-film theme outputs are viewed.

### 8.3 Loss of access after selection

If lawful access disappears before extraction, use a retained copy only when its license permits continued retention and processing. Otherwise, replace the source within its slot. If the bundle falls below the hard minimum, replace the film. Never reconstruct a missing article from snippets or another author's quotations.

## 9. OCR and text preparation

Page images or publisher PDFs are the authoritative representation when available; OCR is a discovery and processing aid. Every OCR-derived source records archive-supplied OCR, local OCR engine and version, language, page range, and whether article boundaries were inferred.

For open or licensed-to-process page images:

1. retain the provider OCR unchanged;
2. run one frozen local OCR pass only if the provider OCR is missing or unusable;
3. preserve page and line coordinates;
4. never silently hand-correct wording in the machine corpus; and
5. require later evidence excerpts to resolve to the archived page image and a stable locator.

If neither provider nor frozen local OCR yields sufficiently coherent article text for exact-evidence verification, classify the candidate `ocr_unusable` and replace it. Poor OCR must not be repaired by asking a language model to guess the original prose.

## 10. Required retrieval record

Create one immutable metadata record per candidate, including excluded candidates. At minimum:

```text
film_id
slot
candidate_rank
selection_status
exclusion_reason
source_id
lineage_id
source_type
article_title
author_display
author_id
outlet
parent_company_at_publication
publication_date
publication_date_precision
publisher
language
word_count_relevant
doi_or_isbn
database_name
database_document_id
canonical_url
permalink_or_archive_locator
query_id
result_rank
access_route
accessed_at_utc
rights_class
processing_permission
retention_deadline
raw_sha256
normalized_text_sha256
ocr_engine_version
page_or_paragraph_locators
duplicate_similarity
lineage_notes
```

Allowed `rights_class` values are:

- `public_domain_verified`
- `open_license_verified`
- `publisher_public_terms_reviewed`
- `subscription_personal_research`
- `subscription_tdm_authorized`
- `permission_granted`
- `rights_unknown`

Only the first six can become included sources, and only when `processing_permission` names the environment in which extraction is allowed. `rights_unknown` is metadata-only until resolved.

## 11. Copyright, licenses, and storage

This section is a conservative research workflow, not legal advice. Copyright and contract questions are evaluated source by source. The U.S. Copyright Office explains that fair use is a case-specific four-factor inquiry and supplies no fixed safe word count or percentage; scholarship and research are relevant purposes but are not automatic exemptions. See the [Copyright Office Fair Use Index](https://www.copyright.gov/fair-use/) and [Fair Use FAQ](https://copyright.gov/help/faq/faq-fairuse.html).

### 11.1 Public repository

The Git repository may contain:

- bibliographic metadata;
- query and selection logs;
- stable URLs, DOIs, archive identifiers, and page locators;
- cryptographic hashes;
- provider and item-level rights statements;
- code and derived nonexpressive variables; and
- limited evidence excerpts when their publication has been reviewed as lawful and necessary.

The repository must not contain subscription PDFs, complete copyrighted articles or chapters, full database exports, paywall cookies, API keys, institutional credentials, or OCR that reconstructs a protected work. There is no universal “safe” excerpt length; public excerpts must be no longer than necessary to make the analytical claim auditable and must not substitute for the source.

### 11.2 Restricted source store

Where retention is authorized, raw files and extracted text are stored outside Git in an encrypted, access-controlled project store. Access is limited to authorized project personnel and the approved extraction service. The store records acquisition source, license, retention deadline, and deletion obligation. Backups inherit the same restrictions.

If an institutional license allows reading but not local corpus creation, store metadata, a provider permalink, and a hash or provider document ID only. Do not create a local full-text copy. [ProQuest's general terms](https://about.proquest.com/en/about/terms-and-conditions/) prohibit automated searches and text/data mining absent a permitted route, while its TDM Studio terms authorize specified mining inside the designated workbench and restrict exports; those distinctions are controlling for ProQuest-acquired text. [EBSCO's standard license](https://legal.ebsco.com/license-agreement) currently prohibits using database content with AI or machine-learning tools, so EBSCO text is metadata/discovery-only for this pipeline unless an executed institutional amendment or written permission expressly allows the use. NYT likewise states that copying or storing TimesMachine articles beyond specified personal, noncommercial use may require permission.

### 11.3 Model-processing gate

Before any text is sent to a model, record:

- whether the provider license permits text and data analysis;
- whether off-platform processing is permitted;
- model host and geographic processing location;
- retention, training, and human-review settings;
- contractual confidentiality or zero-retention protection; and
- whether derived excerpts may be exported.

Licensed source text must not be pasted into a consumer or third-party model merely because the researcher can read it. If off-platform processing is not expressly compatible with the license, use an approved local/institutional environment, an authorized provider workbench, or reject the source as `no_processing_rights`.

### 11.4 Open and public-domain materials

“Available on the web” does not mean public domain. Preserve the item-level license or rights statement. MHDL and Chronicling America provide unusually favorable research access, but both still direct users to rights information, and Chronicling America warns that some less-than-95-year-old pages may contain protected third-party material.

For verified public-domain or permissively licensed items, the private corpus may retain complete OCR and page images. Public redistribution still follows attribution, archive, and license requirements.

## 12. Frozen workflow

For each film, the retrieval process is:

1. Resolve film identity, alternate titles, director, and release-date anchor without theme queries.
2. Load the prespecified access manifest and source hierarchy.
3. Retrieve `C_TRADE`, `C_GENERAL`, `R_LATER`, `S_ACADEMIC`, and `P_SYNOPSIS` independently.
4. Log every query and candidate before model processing.
5. Apply date, provenance, completeness, length, rights, and independence checks.
6. Apply hashes, near-duplicate detection, and lineage rules.
7. Substitute `R_LATER_2` only if the complete academic search fails.
8. Freeze the final bundle manifest and source hashes.
9. Verify that text can lawfully enter the declared extraction environment.
10. Only then release one source at a time to the frozen extraction pipeline.

The extraction pipeline receives no rejected candidates, search-result snippets, box-office rank, hypothesized trend, or lower-priority eligible sources. Retrieval staff do not see film-level theme outputs until all bundles in the relevant development or validation set are locked.

## 13. Coverage and audit outputs

The retrieval report must show, by historical period:

- eligible candidates and selected sources by slot, outlet, archive, and access route;
- target-bundle completion and minimum-bundle completion;
- academic-to-retrospective substitutions;
- access failures separately from true source nonexistence;
- OCR failures and date uncertainty;
- duplicate and lineage collapses;
- use of shortened-source exceptions;
- source and film replacements;
- rights classes and processing environments; and
- time and cost per source.

Coverage failure is itself a pilot result. It must not be repaired after theme results are known. Any new archive, changed outlet order, widened window, relaxed eligibility rule, new query form, or altered bundle minimum is a material amendment. If made after validation retrieval begins, affected validation films become development material and a new untouched validation sample is required.

## 14. Reproducibility note

Search indexes, archive holdings, URLs, licenses, and APIs change. Reproducibility therefore depends on the frozen query log, candidate manifest, provider identifiers, timestamps, hashes, access manifest, and rights record—not on an expectation that a later researcher will see an identical live search page. Before a main study begins, this protocol is rechecked for access feasibility only. Any substantive change is dated and versioned before main-corpus theme retrieval.
