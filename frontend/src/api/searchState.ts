/**
 * Serializing search state to and from a query string.
 *
 * One module owns both directions, and the *same* serializer produces the API
 * request and the browser address bar. That is the point: the URL you can copy
 * out of the address bar is exactly the query that produced the results on
 * screen, so a shared link and a `curl` of the API can never disagree.
 *
 * Parsing is deliberately lenient about values and strict about structure:
 *
 *  - Text and numeric filters are kept as raw strings, even nonsense ones.
 *    The server owns validation, so `?minPrice=abc` should reach it and come
 *    back as a 400 the user can see — not be silently dropped here, which
 *    would show results that don't match the URL.
 *  - `sort` and `dedupe` map to a dropdown and a checkbox that cannot render
 *    an invalid value, so an unrecognized one falls back to the default.
 *  - `page` must be a positive integer to be usable as a number; anything
 *    else means page 1.
 */

import type { SearchFormState, SortOption } from './types'

export const DEFAULT_FORM: SearchFormState = {
  minPrice: '',
  maxPrice: '',
  minBedrooms: '',
  city: '',
  keyword: '',
  targetBudget: '',
  dedupe: false,
  sort: 'relevance',
  pageSize: '5',
}

const SORT_OPTIONS: readonly SortOption[] = [
  'relevance',
  'priceAsc',
  'priceDesc',
  'newest',
] as const

/** Filters that are plain text on the wire and in the form. */
const TEXT_FIELDS = [
  'minPrice',
  'maxPrice',
  'minBedrooms',
  'city',
  'keyword',
  'targetBudget',
] as const satisfies readonly (keyof SearchFormState)[]

export function buildSearchParams(form: SearchFormState, page: number): URLSearchParams {
  const params = new URLSearchParams()

  // Blank inputs are omitted entirely: "no value" must mean "no filter".
  // Note we do NOT validate ranges here — the server owns validation, and
  // duplicating those rules client-side is how the two drift apart.
  for (const name of TEXT_FIELDS) {
    const trimmed = String(form[name]).trim()
    if (trimmed !== '') params.set(name, trimmed)
  }

  params.set('sort', form.sort)
  if (form.dedupe) params.set('dedupe', 'true')
  params.set('page', String(page))
  if (form.pageSize.trim() !== '') params.set('pageSize', form.pageSize.trim())

  return params
}

export interface ParsedSearchState {
  form: SearchFormState
  page: number
}

/** Rebuild form state from a query string (`window.location.search`). */
export function parseSearchState(search: string): ParsedSearchState {
  const params = new URLSearchParams(search)
  const form: SearchFormState = { ...DEFAULT_FORM }

  for (const name of TEXT_FIELDS) {
    const value = params.get(name)
    if (value !== null) form[name] = value
  }

  const pageSize = params.get('pageSize')
  if (pageSize !== null) form.pageSize = pageSize

  const sort = params.get('sort')
  if (sort !== null && (SORT_OPTIONS as readonly string[]).includes(sort)) {
    form.sort = sort as SortOption
  }

  form.dedupe = params.get('dedupe') === 'true'

  const rawPage = Number(params.get('page'))
  const page = Number.isInteger(rawPage) && rawPage >= 1 ? rawPage : 1

  return { form, page }
}

/** The path + query the address bar should show for this state. */
export function searchStateToUrl(form: SearchFormState, page: number): string {
  return `${window.location.pathname}?${buildSearchParams(form, page).toString()}`
}
