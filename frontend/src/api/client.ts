/**
 * The single place HTTP happens. Turns the backend's error envelope into a
 * typed `ApiError`; query-string construction lives in `searchState.ts`.
 */

import { buildSearchParams } from './searchState'
import type { ErrorBody, ErrorDetail, SearchFormState, SearchResponse } from './types'

/** A structured failure; `details` carries per-field issues for the form. */
export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: ErrorDetail[]

  constructor(status: number, body: ErrorBody) {
    super(body.message)
    this.name = 'ApiError'
    this.status = status
    this.code = body.code
    this.details = body.details ?? []
  }

  /** Field-keyed issues, for wiring server validation back to the inputs. */
  fieldIssues(): Record<string, string> {
    const issues: Record<string, string> = {}
    for (const d of this.details) {
      if (d.field) issues[d.field] = d.issue
    }
    return issues
  }

  /** Issues with no field attached (e.g. minPrice > maxPrice spans two). */
  generalIssues(): string[] {
    return this.details.filter((d) => !d.field).map((d) => d.issue)
  }
}

async function request<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, { signal, headers: { Accept: 'application/json' } })

  if (!response.ok) {
    // Parsing is defensive: a proxy or crash could return a non-envelope body.
    let body: ErrorBody = {
      code: 'UNKNOWN',
      message: `Request failed with status ${response.status}`,
      details: [],
    }
    try {
      const parsed = await response.json()
      if (parsed?.error) body = parsed.error as ErrorBody
    } catch {
      // Keep the fallback message.
    }
    throw new ApiError(response.status, body)
  }

  return (await response.json()) as T
}

export function searchListings(
  form: SearchFormState,
  page: number,
  signal?: AbortSignal,
): Promise<SearchResponse> {
  return request<SearchResponse>(
    `/api/listings/search?${buildSearchParams(form, page).toString()}`,
    signal,
  )
}

export function fetchCities(signal?: AbortSignal): Promise<string[]> {
  return request<string[]>('/api/cities', signal)
}
