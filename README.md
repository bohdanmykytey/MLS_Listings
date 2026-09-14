# Listing Search Service

Full-stack search over property listings ingested from multiple MLS feeds.
Filtering, ranking, and pagination are pure functions behind a REST API.

**FastAPI 0.118 · Pydantic v2 · Python 3.13** — **React 19 · TypeScript · Vite 8 · MUI 9**
Requires Python 3.11+ and Node 20+. No database, Docker, or network access after install.

## Running

```bash
./start.sh      # both services; installs on first run, Ctrl-C stops both
```

UI on `:3000`, API on `:8000`, OpenAPI at `:8000/docs`. Vite proxies `/api/*` →
`:8000`, so the browser sees one origin and CORS never engages.

<details>
<summary>Manual equivalent — backend first, the frontend proxies to it</summary>

```bash
cd backend  && python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt \
            && ./.venv/bin/uvicorn app.main:app --reload --port 8000
cd frontend && npm install && npm run dev     # or `npm start` → prod build on :4173
```
</details>

`LISTING_SEARCH_REFERENCE_DATE=YYYY-MM-DD` pins the date days-on-market is
measured against, for reproducible scores.

## Testing

```bash
cd backend  && ./.venv/bin/python -m pytest    # 194
cd frontend && npm test                        # 76  (vitest + RTL, jsdom)
                npm run typecheck && npm run lint
```


Project Features:

- Searches both MLS_A and MLS_B, letting the user see raw results from both feeds or merge duplicates into one.
- Filters on Min Price, Max Price, Min Bedrooms, City, Keyword (matched against the description the API returns), Target Budget (the biggest factor in the relevance score), and results per page. Pagination is server-side rather than client-side — a real deployment in a market like New York could return thousands of rows, and shipping all of them to the browser just to paginate locally doesn't scale.
- Ascending/descending column sorting directly in `ResultsTable.tsx`.
- API-driven architecture: the frontend is purely the View — filtering, ranking, and pagination all live on the backend. Keeps the UI thin and the logic reusable and scalable independent of any one client.
- An explicit Search button instead of auto-fetching on blur. An earlier version fetched as the user typed, but in a real app — especially one billed per request, like an API behind an AWS Lambda — that wastes both compute and money on every keystroke.

What's missing, but has been considered:

- Authentication. A real deployment would put OAuth 2.0 in front of a Lambda authorizer; that's out of scope here, so origins are simply allow-listed in `main.py` instead — not production-grade, but sufficient for this assessment.
- Geo/proximity search. Haversine distance and a radius match are implemented in `geo.py` but not wired up, since it's outside the stated scope. A real version would pair this with something like the Google Maps API, both to plot the target city and to let the user search by latitude/longitude plus a radius.

## API Behavior

The API weighs target price first when producing the relevance score, since
budget is the primary reason a buyer is looking in a given area or
neighborhood at all: `relevance = 100 * (0.6 * budget_fit + 0.4 * negotiability)`.
`budget_fit` decays exponentially with distance from `targetBudget`; `negotiability`
rewards time on market as buyer leverage, not "freshness." The relevance score
is always rendered — an earlier version hid it until a filter was applied, but
the brief lists it as an always-shown minimum field, so that call was
reverted; the column-hiding capability stays in the code (`ResultsTable`'s
`showScore` prop) but is never wired to `false`.

## File guide

Each file's own docstring is the primary source; this is the map between them
and where each stage sits in `filter -> dedupe -> score -> sort -> paginate`.

**Backend** (`backend/app/`)

- `models.py` — The Pydantic contract: request/response shapes, validation
  bounds, and the `SOURCE:ID` composite key every listing is addressed by.
  Everything else in the backend is built to satisfy this file.
- `clock.py` — Injects "today" as a value instead of letting scoring call
  `date.today()` directly, so days-on-market — and every score — stays
  reproducible in tests and demos via `LISTING_SEARCH_REFERENCE_DATE`.
- `repository.py` — Loads the JSON feed once into memory and exposes it
  through a read-only `ListingRepository` protocol; the rest of the app
  depends on that interface, not the JSON file, so swapping in a real
  database later is a one-class, one-line change.
- `filters.py` — Independent, pure predicates (price, bedrooms, city,
  keyword, status) whose conjunction narrows the candidate set. Runs first
  in the pipeline because scoring is the expensive stage and there's no
  reason to rank rows the user excluded.
- `dedupe.py` — Collapses the same physical property arriving from both MLS
  feeds, clustering on rounded coordinates + bedrooms + sqft (address text
  disagrees between feeds, so it isn't trusted). Runs before scoring because
  a merged listing's effective date becomes the *earliest* one in its
  cluster, which is an input to negotiability, not just cosmetic cleanup.
- `scoring.py` — The relevance formula itself: `budget_fit` and
  `negotiability`, weighted and combined into the 0-100 score, plus the
  deterministic tie-break chain (score desc, longest-on-market, cheapest,
  composite key) used when two listings tie.
- `pagination.py` — Slices one page out of an already-sorted list and reports
  accurate totals; a page past the end is a valid empty page, not an error.
  Runs last because `total` must count matches, not one page's length.
- `search.py` — Composes the five stages above in one place so their order
  is explicit and readable rather than implied by an endpoint handler.
- `api.py` — The thin HTTP layer: validates via `SearchParams`, calls
  `search.py`, serializes the result. No filtering, scoring, or pagination
  logic lives here on purpose.
- `errors.py` — Normalizes every non-2xx response (validation, 404, 500)
  into one `ErrorEnvelope` shape, and reports validation failures as 400
  (not FastAPI's default 422) to match how the brief frames bad input.
- `geo.py` — Haversine distance + radius-match helpers. No requirement asks
  for radius search, so this is intentionally unwired — implemented ahead of
  time because it's easy to get subtly wrong, kept out of `SearchParams`
  because shipping an untested public parameter is worse than shipping none.
- `main.py` — Wires the FastAPI app together: registers the router and error
  handlers, configures CORS for the Vite dev/preview ports.

**Frontend** (`frontend/src/`)

- `main.tsx` — Entry point: mounts `App` under a minimal MUI theme.
- `App.tsx` — Composition root. Owns no search logic itself, just picks
  which of error/loading/empty/results to render, in that precedence, so two
  states can never be shown on top of each other.
- `api/types.ts` — Hand-mirrors `backend/app/models.py`. Kept manual rather
  than generated since the contract is small; the backend is the source of
  truth if they ever drift.
- `api/client.ts` — The one place `fetch` happens. Turns the backend's error
  envelope into a typed `ApiError` so the rest of the UI never re-parses JSON.
- `api/searchState.ts` — The single serializer between form state, the API
  query string, and the browser address bar, so a copied URL always
  reproduces exactly the results it was copied from.
- `hooks/useListingSearch.ts` — Owns the request lifecycle. Splits `form`
  (the draft the inputs are bound to) from `submitted` (what actually
  produced the results and the URL); only an explicit action — Search,
  Enter, a page click, or Reset — moves one into the other and fires a
  request. Also does the stale-while-revalidate caching (50-entry LRU, keyed
  by query string) and aborts a superseded in-flight request before
  committing a new one.
- `components/SearchForm.tsx` — The filter inputs, wrapped in a real
  `<form>` so Enter submits like any other search box. Editing a field only
  ever touches the draft; nothing is fetched until submission.
- `components/ResultsTable.tsx` — Renders the ranked rows plus the score's
  two components, so a rank is explainable rather than opaque. Column
  headers sort the *current page only* — relevance still decides which rows
  reach the page at all — kept client-side since it needs no round trip.
- `components/PaginationBar.tsx` — Page controls driven by the server's
  `pageInfo`, not `items.length`, so the count describes the whole result
  set rather than just the visible page.
- `components/StateViews.tsx` — Loading/empty/error views, kept out of
  `ResultsTable` so exactly one of "table," "spinner," "empty," or "error"
  ever renders — and so a rejected query (400) stays visually distinct from
  a valid query that matched nothing.


