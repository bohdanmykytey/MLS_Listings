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


API Behavior:

The api takes into target price when producing the (relevence) score first and foremost as the budget and cost is the primary driving reason for looking in a certain area, neighborhood, etc. 
also the score is not displayed (hidden from the DOM) until the user starts to use the filters on the UI (which translate to query params) 


