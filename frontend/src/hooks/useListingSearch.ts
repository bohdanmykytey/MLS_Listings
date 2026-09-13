/**
 * Owns the search request lifecycle so components stay presentational.
 *
 * Five things this exists to get right:
 *
 *  - Stale responses. Typing fires overlapping requests, and they can resolve
 *    out of order, so an older response could overwrite a newer one. Each run
 *    aborts the previous one and re-checks that it is still current before
 *    committing state.
 *  - Page resets. Changing a filter while on page 3 would otherwise request
 *    page 3 of a different result set. Filter edits reset to page 1; only the
 *    pager moves pages.
 *  - Exactly one of loading / error / empty / results is true at a time, so
 *    the UI can't render a spinner over a stale error.
 *  - The address bar reflects the search, so a result set can be shared,
 *    bookmarked, reloaded, and walked with the back button.
 *  - Repeated queries render from cache instead of flashing a spinner.
 *
 * Caching strategy is stale-while-revalidate: a cached response paints
 * immediately, and the network request still goes out to confirm it. When the
 * fresh response is identical the cached object is kept by reference, so React
 * re-renders nothing. The user sees instant navigation; correctness is not
 * traded away for it, which a cache-only strategy would do the moment a
 * listing changed underneath us.
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

const DEBOUNCE_MS = 300

/** Bounded so a long session can't grow the cache without limit. */
const MAX_CACHE_ENTRIES = 50

/**
 * Structural comparison of two responses.
 *
 * Used to decide whether a revalidation actually changed anything. Comparing
 * serialized JSON is sound here because both values come from the same server
 * serializer, so key order is stable — and the payload is one page of results,
 * not a large document. For bigger responses this would become a field-by-field
 * comparison or a server-provided ETag.
 */
export function sameResponse(a: SearchResponse | null, b: SearchResponse | null): boolean {
  if (a === b) return true
  if (!a || !b) return false
  return JSON.stringify(a) === JSON.stringify(b)
}

export interface UseListingSearch {
  form: SearchFormState
  page: number
  data: SearchResponse | null
  loading: boolean
  error: ApiError | null
  /** Patch one or more filters; always returns to page 1. */
  updateForm: (patch: Partial<SearchFormState>) => void
  goToPage: (page: number) => void
  reset: () => void
  retry: () => void
}

export function useListingSearch(): UseListingSearch {
  // The initial search comes from the URL, so a shared or bookmarked link
  // opens on the results it promised rather than on defaults.
  const [initial] = useState(() => parseSearchState(window.location.search))

  const [form, setForm] = useState<SearchFormState>(initial.form)
  const [page, setPage] = useState(initial.page)
  const [data, setData] = useState<SearchResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<ApiError | null>(null)
  // Bumped to force a re-fetch with identical inputs (the retry button).
  const [attempt, setAttempt] = useState(0)

  const inFlight = useRef<AbortController | null>(null)
  const cache = useRef(new Map<string, SearchResponse>())

  // How the next state change should affect history, and whether it came from
  // the browser's own back/forward (in which case we must not write at all).
  const historyMode = useRef<'push' | 'replace'>('replace')
  const restoringFromHistory = useRef(false)
  const hasMounted = useRef(false)

  /** Keep the cached object when nothing changed, so React skips the render. */
  const commit = useCallback((response: SearchResponse) => {
    setData((prev) => (sameResponse(prev, response) ? prev : response))
    setError(null)
  }, [])

  // --- keep the address bar in step with the search ------------------------
  useEffect(() => {
    // Don't rewrite a clean "/" on first paint, and don't fight the browser
    // when the user is the one navigating.
    if (!hasMounted.current) {
      hasMounted.current = true
      return
    }
    if (restoringFromHistory.current) {
      restoringFromHistory.current = false
      return
    }

    const url = searchStateToUrl(form, page)
    if (url === window.location.pathname + window.location.search) return

    // Typing replaces, so one filter word doesn't become eight history entries;
    // deliberate navigation (paging, reset) pushes, so back undoes one step.
    if (historyMode.current === 'push') window.history.pushState(null, '', url)
    else window.history.replaceState(null, '', url)

    historyMode.current = 'replace'
  }, [form, page])

  // --- back / forward ------------------------------------------------------
  useEffect(() => {
    const onPopState = () => {
      const restored = parseSearchState(window.location.search)
      restoringFromHistory.current = true
      setForm(restored.form)
      setPage(restored.page)
    }
    window.addEventListener('popstate', onPopState)
    return () => window.removeEventListener('popstate', onPopState)
  }, [])

  // --- fetching ------------------------------------------------------------
  useEffect(() => {
    const key = buildSearchParams(form, page).toString()
    const cached = cache.current.get(key)

    if (cached) {
      // Paint immediately; the request below confirms it.
      commit(cached)
      setLoading(false)
    } else {
      setLoading(true)
    }

    const timer = setTimeout(() => {
      inFlight.current?.abort()
      const controller = new AbortController()
      inFlight.current = controller

      searchListings(form, page, controller.signal)
        .then((response) => {
          if (controller.signal.aborted) return

          // Re-insert to move this key to the end: Map preserves insertion
          // order, so the oldest key is the first one out when we trim.
          cache.current.delete(key)
          cache.current.set(key, response)
          if (cache.current.size > MAX_CACHE_ENTRIES) {
            cache.current.delete(cache.current.keys().next().value as string)
          }

          commit(response)
        })
        .catch((err: unknown) => {
          if (controller.signal.aborted) return
          // An invalid query has no valid result set; clearing `data` prevents
          // showing rows that don't match what the inputs now say. A failed
          // query is also dropped from the cache so a retry really retries.
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
    }, DEBOUNCE_MS)

    return () => clearTimeout(timer)
  }, [form, page, attempt, commit])

  useEffect(() => () => inFlight.current?.abort(), [])

  const updateForm = useCallback((patch: Partial<SearchFormState>) => {
    historyMode.current = 'replace'
    setForm((prev) => ({ ...prev, ...patch }))
    setPage(1)
  }, [])

  const goToPage = useCallback((next: number) => {
    historyMode.current = 'push'
    setPage(next)
  }, [])

  const reset = useCallback(() => {
    historyMode.current = 'push'
    setForm(DEFAULT_FORM)
    setPage(1)
  }, [])

  const retry = useCallback(() => setAttempt((n) => n + 1), [])

  return { form, page, data, loading, error, updateForm, goToPage, reset, retry }
}
