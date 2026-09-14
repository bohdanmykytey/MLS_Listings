/**
 * Owns the search request lifecycle so components stay presentational.
 *
 * Search is explicit: typing only updates the `form` draft. Nothing fetches
 * or touches the URL until the user submits (Search, Enter, a page click, or
 * Reset) — `submitted` is the query that actually produced what's on screen.
 * A debounced auto-fetch was tried earlier and dropped: a still-typing user
 * hasn't finished stating their query, so fetching mid-keystroke is wasted work.
 *
 * Also handles: aborting a superseded in-flight request before committing a
 * new one, resetting to page 1 on every new search, keeping the address bar
 * in sync with `submitted` (not the draft) so links/reload/back-forward all
 * work, and a stale-while-revalidate cache keyed by query string.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, searchListings } from '../api/client'
import {
  DEFAULT_FORM,
  buildSearchParams,
  parseSearchState,
  searchStateToUrl,
} from '../api/searchState'
import type { SearchFormState, SearchResponse } from '../api/types'

export { DEFAULT_FORM }

/** Bounded so a long session can't grow the cache without limit. */
const MAX_CACHE_ENTRIES = 50

/** Structural equality, so an unchanged revalidation keeps the same
 *  object reference and React re-renders nothing. */
export function sameResponse(a: SearchResponse | null, b: SearchResponse | null): boolean {
  if (a === b) return true
  if (!a || !b) return false
  return JSON.stringify(a) === JSON.stringify(b)
}

export interface UseListingSearch {
  /** The draft the inputs are bound to. Not yet searched. */
  form: SearchFormState
  /** The page of the *submitted* query currently on screen. */
  page: number
  data: SearchResponse | null
  loading: boolean
  error: ApiError | null
  /** Patch the draft. Does not search or touch the URL. */
  updateForm: (patch: Partial<SearchFormState>) => void
  /** Submit the draft: it becomes the query, page resets to 1, and it fetches. */
  runSearch: () => void
  goToPage: (page: number) => void
  /** Clear the draft and immediately search with it. */
  reset: () => void
  retry: () => void
}

export function useListingSearch(): UseListingSearch {
  // Initial search comes from the URL, so a shared/bookmarked link opens on
  // the results it promised. The draft starts equal to it.
  const [initial] = useState(() => parseSearchState(window.location.search))

  const [form, setForm] = useState<SearchFormState>(initial.form)
  const [submitted, setSubmitted] = useState<SearchFormState>(initial.form)
  const [page, setPage] = useState(initial.page)
  const [data, setData] = useState<SearchResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<ApiError | null>(null)
  // Bumped to force a re-fetch of an unchanged query (the retry button).
  const [attempt, setAttempt] = useState(0)

  const inFlight = useRef<AbortController | null>(null)
  const cache = useRef(new Map<string, SearchResponse>())

  // True while a submitted/page change came from popstate — the URL already
  // matches it, so the sync effect below must not rewrite it.
  const restoringFromHistory = useRef(false)
  const hasMounted = useRef(false)

  /** Keep the cached object when nothing changed, so React skips the render. */
  const commit = useCallback((response: SearchResponse) => {
    setData((prev) => (sameResponse(prev, response) ? prev : response))
    setError(null)
  }, [])

  // Push one history entry per deliberate action (search/page/reset/restore).
  useEffect(() => {
    if (!hasMounted.current) {
      hasMounted.current = true // don't rewrite a clean "/" on first paint
      return
    }
    if (restoringFromHistory.current) {
      restoringFromHistory.current = false
      return
    }

    const url = searchStateToUrl(submitted, page)
    if (url === window.location.pathname + window.location.search) return

    window.history.pushState(null, '', url)
  }, [submitted, page])

  useEffect(() => {
    const onPopState = () => {
      const restored = parseSearchState(window.location.search)
      restoringFromHistory.current = true
      setForm(restored.form)
      setSubmitted(restored.form)
      setPage(restored.page)
    }
    window.addEventListener('popstate', onPopState)
    return () => window.removeEventListener('popstate', onPopState)
  }, [])

  // Depends on `submitted`, never on `form`: a draft edit must not fetch.
  useEffect(() => {
    const key = buildSearchParams(submitted, page).toString()
    const cached = cache.current.get(key)

    if (cached) {
      commit(cached) // paint immediately; the request below confirms it
      setLoading(false)
    } else {
      setLoading(true)
    }

    inFlight.current?.abort()
    const controller = new AbortController()
    inFlight.current = controller

    searchListings(submitted, page, controller.signal)
      .then((response) => {
        if (controller.signal.aborted) return

        // Re-insert to move this key to the end (Map preserves insertion
        // order), so the oldest key is evicted first.
        cache.current.delete(key)
        cache.current.set(key, response)
        if (cache.current.size > MAX_CACHE_ENTRIES) {
          cache.current.delete(cache.current.keys().next().value as string)
        }

        commit(response)
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return
        // Drop from cache too, so a retry actually retries.
        cache.current.delete(key)
        setData(null)
        setError(
          err instanceof ApiError
            ? err
            : new ApiError(0, {
                code: 'NETWORK_ERROR',
                message: 'Could not reach the search service. Is the API running?',
                details: [],
              }),
        )
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
  }, [submitted, page, attempt, commit])

  useEffect(() => () => inFlight.current?.abort(), [])

  const updateForm = useCallback((patch: Partial<SearchFormState>) => {
    setForm((prev) => ({ ...prev, ...patch }))
  }, [])

  const runSearch = useCallback(() => {
    // New object even if unchanged, so a repeat Search click still re-fetches.
    setSubmitted({ ...form })
    setPage(1)
  }, [form])

  const goToPage = useCallback((next: number) => {
    setPage(next)
  }, [])

  const reset = useCallback(() => {
    setForm(DEFAULT_FORM)
    setSubmitted({ ...DEFAULT_FORM })
    setPage(1)
  }, [])

  const retry = useCallback(() => setAttempt((n) => n + 1), [])

  return { form, page, data, loading, error, updateForm, runSearch, goToPage, reset, retry }
}
