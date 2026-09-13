# Listing Search Service

Full-stack search over property listings ingested from multiple MLS feeds.
Filtering, relevance ranking, and pagination are implemented as pure functions
behind a REST API.

**FastAPI 0.118 · Pydantic v2 · Python 3.13** — **React 19 · TypeScript · Vite 8 · MUI 9**

Requires Python 3.11+ and Node 20+. No database, Docker, or network access
after install.

## Running

```bash
./start.sh      # both services; installs on first run, Ctrl-C stops both
                # use this command to run both as one from the parent folder, otherwise,
                # see instructions below to run the front and back end's individually 
```

UI on `:3000`, API on `:8000`, OpenAPI at `:8000/docs`. Vite proxies `/api/*` →
`:8000` in dev and preview, so the browser sees one origin and CORS never
engages.

<details>
<summary>Manual equivalent — backend first, the frontend proxies to it</summary>

```bash
cd backend  && python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt \
            && ./.venv/bin/uvicorn app.main:app --reload --port 8000
cd frontend && npm install && npm run dev     # or `npm start` → prod build on :4173
```
</details>

`LISTING_SEARCH_REFERENCE_DATE=YYYY-MM-DD` pins the recency reference date for
reproducible scores; `start.sh` defaults it to today.

## Testing

```bash
cd backend  && ./.venv/bin/python -m pytest    # 215
cd frontend && npm test                        # 72  (vitest + RTL, jsdom)
                npm run typecheck && npm run lint
```

287 total. Backend suites mirror modules (`scoring`, `filters`, `pagination`,
`dedupe`, `search`, `validation`, `api`, `repository`, `geo`); API tests use
`TestClient` with a per-test repository fixture. Frontend covers serialization
round-trips, each component, and `App` end-to-end against a stubbed `fetch`, so
the real client and error-parsing code run. An autouse fixture pins the clock,
so score assertions are exact values rather than tolerances.

Edge cases named in the brief:

| Case | Covered by |
| --- | --- |
| No matches | `test_validation.py`, `test_search.py::TestEmptyResults` |
| Tied scores | `test_scoring.py::TestTieBreaking` |
| Invalid filter values | `test_validation.py` — 16-case parametrized matrix |
| Pagination boundaries | `test_pagination.py::TestBoundaries`, `TestPageWalkIsLossless` |

**Score ties are real, not hypothetical.** Scores are rounded to 2dp before
sorting, so two listings whose raw scores differ by less than half a cent tie
in the ordering. `targetBudget=418000` ties `MLS_B:B7` and `MLS_A:A5` at 84.11
on the sample data. Both rows still render, both still show 84.11 — the
tie-break decides only which comes first. Without a total order the two can
swap between requests, and since each page is an independent request, a
straddling pair means one listing appears on two pages and the other on none.
`TestTieBreaking` covers both the real case and constructed fixtures that
isolate each link in the chain.

**Pagination is tested as a property** — walk every page at eight page sizes,
assert each item appears exactly once. That catches unstable-sort drift, which
spot-checking three pages does not.

## Relevance scoring

Computed server-side in `backend/app/scoring.py`. The client renders
`relevanceScore` and `scoreBreakdown` as returned and performs no scoring
arithmetic.

```
relevance = 100 × (0.6 × budget_fit + 0.4 × recency)
```

**`budget_fit`** — 1.0 within ±5% of `targetBudget`, decaying linearly to 0.0
at ±50%. The penalty is **symmetric**: buyers shop a band, not a ceiling, so a
$200k home does not fit a $500k budget better than an $800k one. Rewarding
anything under budget — the obvious alternative — ranks a studio above the
house the user actually wants.

**`recency`** — exponential decay, 30-day half-life. Smooth, monotone, never
negative. Linear decay across the corpus range would tie every score to the
dataset's oldest record, so one stale listing reshuffles every rank.

**No `targetBudget`** — the budget term is dropped and recency renormalizes to
full weight, keeping scores on the same 0–100 scale.

**Ties** break deterministically: score desc → newest → cheapest → `source:id`.
Without a total order, equal-scoring rows swap between requests and the same
listing appears on two pages.

Every response carries a `scoreBreakdown`, so a rank is explainable rather than
an opaque number.

## Architecture

Search is a pure pipeline — `filter → score → dedupe → sort → paginate` — with
no I/O or framework types, so it is testable without a server. The order is
load-bearing: filter before score (don't rank excluded rows); dedupe after
score (the survivor keeps its own correct score, and `mergedFrom` is reported
on the visible row); sort before paginate (slicing an unordered list drifts
rows between pages); paginate last (`total` counts matches, not the page).

`ListingRepository` is a `Protocol`. The in-memory implementation loads the
JSON feed at startup; swapping in Postgres is one class and one line in
`main.py`.

Listings are keyed by composite `SOURCE:ID` throughout — API paths, dedupe
references, React list keys — because the brief states `id` is unique per
source only.

**All filtering, ranking, and pagination is server-side.** The client submits
query parameters and renders the response; it derives only two presentational
values — the `Showing 6–10 of 12` label from `pageInfo`, and the colour band on
the score chip.

## API

| Method | Path | |
| --- | --- | --- |
| `GET` | `/api/health` | Liveness + active reference date |
| `GET` | `/api/cities` | Distinct cities, for the UI dropdown |
| `GET` | `/api/listings/search` | Filter, rank, paginate |
| `GET` | `/api/listings` | All listings (raw) |
| `GET` | `/api/listings/{source}/{id}` | Single listing |
| `POST` | `/api/listings` | Create (409 if the key exists) |
| `PUT` | `/api/listings/{source}/{id}` | Replace |
| `DELETE` | `/api/listings/{source}/{id}` | Delete |

Search parameters: `minPrice`, `maxPrice`, `minBedrooms`, `city`, `keyword`,
`targetBudget`, `status`, `dedupe`, `sort`, `page`, `pageSize`.

### Errors

Every non-2xx response uses one envelope, so the UI needs a single parser:

```json
{ "error": { "code": "INVALID_REQUEST", "message": "...", "details": [
  { "field": "pageSize", "issue": "Input should be greater than or equal to 1" } ] } }
```

Invalid input is **400**, not FastAPI's default 422 — the brief frames these as
bad requests. `details[].field` uses the alias the client sent (`pageSize`, not
`page_size`) so the form can highlight the offending input.

A valid query matching nothing is **not** an error: `200` with empty `items`
and `total: 0`. A page past the end returns an empty page with accurate
`totalPages` so the UI can clamp.

## Deduplication (`?dedupe=true`)

The sample data contains four cross-source duplicate pairs — the same property
from `MLS_A` and `MLS_B` with different address formatting, prices, and in one
case a different zip. Records cluster on `(lat≈, lng≈, bedrooms, sqft)`:
address text is explicitly not normalized ("St"/"Street", "Apt"/"Unit") and
zips disagree, so geometry and physical facts are the only stable signal. Price
and date are excluded from the key — those are precisely what feeds disagree
on. The most recently listed record survives and reports what it absorbed in
`mergedFrom`.

**Off by default**, because the stated requirements describe searching the raw
feed union; collapsing by default would change the implied result counts.

## URL state & caching

Search state lives in the query string, so results are shareable, bookmarkable,
reload-safe, and back/forward-navigable:

```
/?city=Springfield&minBedrooms=3&targetBudget=500000&page=2&pageSize=5
```

**One serializer builds both the address bar and the API request**
(`api/searchState.ts`). The copied URL is provably the query that produced the
rendered results, so a shared link and a `curl` cannot disagree.

- `replaceState` on filter edits, `pushState` on page change and reset —
  otherwise a seven-character keyword costs seven presses of back.
- Invalid values survive the round trip (`?minPrice=abc` → a 400 the user
  sees). Dropping them would render results contradicting the URL. `sort` and
  `dedupe` are exceptions: they back a `<select>` and a checkbox, which cannot
  render an unknown value, so they fall back to defaults.

Responses are cached in memory keyed by query string,
**stale-while-revalidate**: a hit paints immediately, the request still goes
out, and if the fresh payload is structurally identical the cached object is
retained *by reference* so React skips the re-render. Not cache-only — that
would serve a price that changed underneath us. 50 entries, LRU eviction;
failures are never cached so retry actually retries.

Request hygiene: 300 ms debounce, `AbortController` per run with a post-resolve
currency check (overlapping requests can resolve out of order), and filter
edits reset to page 1.

## Scope

**In, unrequested:** CRUD (makes the repository seam real — reads and writes
share one interface), `?dedupe=true`, `/api/cities`, URL state sync, response
caching.

**Out, deliberately:** no database, auth, or Docker — 12 read-mostly records
and a brief asking for a runnable app, not infrastructure. No generated API
client; the surface is small enough that a hand-maintained `types.ts` mirroring
`models.py` is less machinery than codegen. No SSR or router — one view. Geo
radius is prepared but unwired.

### Trade-offs

| Decision | Rationale |
| --- | --- |
| One error envelope for every non-2xx | FastAPI would otherwise emit three shapes (`detail` array, `detail` string, HTML 500) and the UI would need three parsers. |
| No client-side range validation | Duplicating rules is how client and server drift. The client sends what was typed and renders the server's verdict. |
| Injectable clock | Recency depends on "today"; reading the clock inside the formula makes tests time-dependent and demos drift. |
| `city` exact-match, not substring | "Fair" must not silently return Fairfax results. |
| Status filterable, unfiltered by default | The brief never asks to hide the single `pending` listing. |

### Extension seams

- **Geo radius** — `app/geo.py` implements and tests haversine +
  `within_radius`, unexposed by design. Add `lat`/`lng`/`radiusMiles` to
  `SearchParams` (validated as a group), add one clause to
  `filters.apply_filters`.
- **Hide non-active** — flip the `SearchParams.status` default to `[ACTIVE]`.
- **Re-weight scoring** — `BUDGET_WEIGHT`, `RECENCY_WEIGHT`,
  `RECENCY_HALF_LIFE_DAYS` are named constants; promoting them to query
  parameters is one field plus one threaded argument.
- **New filter / sort** — predicate + conjunction clause, or a branch in
  `search._sort` (keep the order total).
- **Persistence** — implement `ListingRepository`, swap one line in `main.py`.

### Known limitations

- **Keyword match is lexical.** `keyword=pets` matches "no pets"; five sample
  descriptions mention pets, three negatively. Pinned as a test
  (`test_known_limitation_lexical_match_ignores_negation`) so it is documented
  behaviour and any fix must change it deliberately.
- **Cross-feed city/zip inconsistencies are not reconciled.** Dedupe sidesteps
  this by matching on geometry.
- **Cache is per-tab, in-memory, with no write invalidation.** A CRUD write
  leaves cached searches stale until revalidation.
- **Scoring is O(n) over filtered rows.** Fine at this size; at real volume the
  budget/recency terms become an index-assisted prefilter with scoring on top-K.
- **No write concurrency control.** The in-memory store has no locking.
- **Bundle ~518 kB unsplit**, almost entirely MUI. Production would code-split.
# MLS_Listings
