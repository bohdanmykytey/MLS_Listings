/**
 * Search-state serialization, both directions.
 *
 * This is the frontend's half of the contract: blank inputs must be omitted
 * so "no value" means "no filter" rather than being sent as an empty string
 * the server would have to interpret. The same serializer drives the address
 * bar, so a round trip must be lossless.
 */

import { describe, expect, it } from 'vitest'
import { DEFAULT_FORM, buildSearchParams, hasActiveFilters, parseSearchState } from './searchState'
import type { SearchFormState } from './types'

describe('buildSearchParams', () => {
  it('omits every blank filter', () => {
    const params = buildSearchParams(DEFAULT_FORM, 1)
    for (const name of ['minPrice', 'maxPrice', 'minBedrooms', 'city', 'keyword', 'targetBudget']) {
      expect(params.has(name)).toBe(false)
    }
  })

  it('always sends page and pageSize', () => {
    const params = buildSearchParams(DEFAULT_FORM, 3)
    expect(params.get('page')).toBe('3')
    expect(params.get('pageSize')).toBe('5')
  })

  it('trims whitespace and includes real values', () => {
    const params = buildSearchParams(
      { ...DEFAULT_FORM, city: '  Reston  ', minPrice: '400000' },
      1,
    )
    expect(params.get('city')).toBe('Reston')
    expect(params.get('minPrice')).toBe('400000')
  })

  it('only sends dedupe when enabled', () => {
    expect(buildSearchParams(DEFAULT_FORM, 1).has('dedupe')).toBe(false)
    expect(buildSearchParams({ ...DEFAULT_FORM, dedupe: true }, 1).get('dedupe')).toBe('true')
  })

  it('sends out-of-range values rather than silently fixing them', () => {
    // The server owns validation; the client must not mask a bad query by
    // quietly correcting it, or the user never sees the error.
    const params = buildSearchParams(
      { ...DEFAULT_FORM, minPrice: '900000', maxPrice: '100000', pageSize: '0' },
      1,
    )
    expect(params.get('minPrice')).toBe('900000')
    expect(params.get('maxPrice')).toBe('100000')
    expect(params.get('pageSize')).toBe('0')
  })
})

describe('parseSearchState', () => {
  it('returns defaults for an empty query string', () => {
    expect(parseSearchState('')).toEqual({ form: DEFAULT_FORM, page: 1 })
  })

  it('restores every filter from a shared link', () => {
    const { form, page } = parseSearchState(
      '?minPrice=400000&maxPrice=600000&minBedrooms=3&city=Reston&keyword=pool' +
        '&targetBudget=500000&dedupe=true&page=2&pageSize=10',
    )
    expect(form).toEqual({
      minPrice: '400000',
      maxPrice: '600000',
      minBedrooms: '3',
      city: 'Reston',
      keyword: 'pool',
      targetBudget: '500000',
      dedupe: true,
      pageSize: '10',
    })
    expect(page).toBe(2)
  })

  it('treats a missing dedupe parameter as off', () => {
    expect(parseSearchState('?city=Reston').form.dedupe).toBe(false)
  })

  it('keeps invalid filter values so the server can reject them', () => {
    // Dropping these would show results that contradict the URL; the user
    // should see the same 400 they would get from the API directly.
    const { form } = parseSearchState('?minPrice=abc&pageSize=0')
    expect(form.minPrice).toBe('abc')
    expect(form.pageSize).toBe('0')
  })

  it.each(['0', '-3', 'two', '1.5', ''])('treats page=%s as page 1', (value) => {
    expect(parseSearchState(`?page=${value}`).page).toBe(1)
  })

  it('ignores parameters it does not recognise', () => {
    expect(parseSearchState('?utm_source=email&city=Vienna').form.city).toBe('Vienna')
  })
})

describe('round trip', () => {
  const cases: Array<[string, SearchFormState, number]> = [
    ['defaults', DEFAULT_FORM, 1],
    ['every field set', {
      minPrice: '400000',
      maxPrice: '600000',
      minBedrooms: '3',
      city: 'Reston',
      keyword: 'pool',
      targetBudget: '500000',
      dedupe: true,
      pageSize: '25',
    }, 4],
    ['partial', { ...DEFAULT_FORM, city: 'Vienna', minBedrooms: '2' }, 2],
  ]

  it.each(cases)('survives build -> parse unchanged (%s)', (_label, form, page) => {
    const parsed = parseSearchState(`?${buildSearchParams(form, page).toString()}`)
    expect(parsed.form).toEqual(form)
    expect(parsed.page).toBe(page)
  })

  it('trims on the way out, so a round trip normalises whitespace', () => {
    const messy = { ...DEFAULT_FORM, city: '  Reston  ' }
    const parsed = parseSearchState(`?${buildSearchParams(messy, 1).toString()}`)
    expect(parsed.form.city).toBe('Reston')
  })
})

describe('hasActiveFilters', () => {
  it('is false for the default, untouched form', () => {
    expect(hasActiveFilters(DEFAULT_FORM)).toBe(false)
  })

  it('ignores pageSize — a display preference, not a filter', () => {
    expect(hasActiveFilters({ ...DEFAULT_FORM, pageSize: '25' })).toBe(false)
  })

  it('is false for whitespace-only text, same as buildSearchParams', () => {
    expect(hasActiveFilters({ ...DEFAULT_FORM, city: '   ', keyword: '  ' })).toBe(false)
  })

  it.each([
    ['minPrice', '400000'],
    ['maxPrice', '600000'],
    ['minBedrooms', '3'],
    ['city', 'Reston'],
    ['keyword', 'garage'],
    ['targetBudget', '500000'],
  ] as const)('is true once %s is set', (field, value) => {
    expect(hasActiveFilters({ ...DEFAULT_FORM, [field]: value })).toBe(true)
  })

  it('is true once dedupe is enabled, even with no other filter set', () => {
    expect(hasActiveFilters({ ...DEFAULT_FORM, dedupe: true })).toBe(true)
  })
})
