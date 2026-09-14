/**
 * Serializes search state to and from a query string. One serializer drives
 * both the API request and the address bar, so a copied URL always
 * reproduces the results it was copied from.
 *
 * Parsing is lenient about values, strict about structure: `?minPrice=abc`
 * reaches the server as-is and comes back a visible 400, rather than being
 * silently dropped here.
 */

import type { SearchFormState } from './types'

export const DEFAULT_FORM: SearchFormState = {
  minPrice: '',
  maxPrice: '',
  minBedrooms: '',
  city: '',
  keyword: '',
  targetBudget: '',
  dedupe: false,
  pageSize: '5',
}

/** Filters that are plain text on the wire and in the form. */
const TEXT_FIELDS = [
  'minPrice',
  'maxPrice',
  'minBedrooms',
  'city',
  'keyword',
  'targetBudget',
] as const satisfies readonly (keyof SearchFormState)[]

/**
 * Has the user specified any actual search criteria? `page`/`pageSize` don't
 * count — those are navigation, not criteria. Currently unwired (an earlier
 * version used it to hide the score column, since reverted) but kept as a
 * tested primitive.
 */
export function hasActiveFilters(form: SearchFormState): boolean {
  const params = buildSearchParams(form, 1)
  return TEXT_FIELDS.some((name) => params.has(name)) || form.dedupe
}

export function buildSearchParams(form: SearchFormState, page: number): URLSearchParams {
  const params = new URLSearchParams()

  // Blank means "no filter"; ranges aren't validated here — the server owns that.
  for (const name of TEXT_FIELDS) {
    const trimmed = String(form[name]).trim()
    if (trimmed !== '') params.set(name, trimmed)
  }

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

  form.dedupe = params.get('dedupe') === 'true'

  const rawPage = Number(params.get('page'))
  const page = Number.isInteger(rawPage) && rawPage >= 1 ? rawPage : 1

  return { form, page }
}

/** The path + query the address bar should show for this state. */
export function searchStateToUrl(form: SearchFormState, page: number): string {
  return `${window.location.pathname}?${buildSearchParams(form, page).toString()}`
}
